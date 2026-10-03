"""Persistent worker loop.

Runs inside the FastAPI process (started from the application lifespan) - it is
NOT a request-scoped BackgroundTask. Production runs exactly one process and one
worker loop, so "one Gemini inference at a time" holds globally.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid

from app.core.config import settings
from app.core.enums import JobStatus, WorkerStatus
from app.core.logging import clear_log_context, get_logger, set_log_context
from app.core.timeutils import utcnow
from app.db.session import session_scope
from app.repositories.jobs import JobRepository
from app.repositories.workers import WorkerStateRepository
from app.services.jobs.orchestrator import JobOrchestrator
from app.worker.recovery import recover_stale_jobs

logger = get_logger(__name__)


class WorkerLoop:
    """Claims queued jobs and processes them one at a time."""

    def __init__(
        self,
        *,
        orchestrator: JobOrchestrator,
        worker_id: str | None = None,
        poll_interval_seconds: float | None = None,
        recovery_interval_seconds: float = 30.0,
    ) -> None:
        self.orchestrator = orchestrator
        self.worker_id = worker_id or settings.worker_id
        self.poll_interval_seconds = poll_interval_seconds or settings.worker_poll_interval_seconds
        self.recovery_interval_seconds = recovery_interval_seconds

        self._task: asyncio.Task | None = None
        self._stopping = asyncio.Event()
        self._current_job_id: uuid.UUID | None = None
        self._current_stage: str | None = None
        self._last_recovery_at: float = 0.0
        self._started = False

    # ---------------------------------------------------------------- lifecycle
    async def start(self) -> None:
        if self._started:
            return
        await self._write_heartbeat(WorkerStatus.STARTING)
        try:
            recovered = await recover_stale_jobs()
            if recovered:
                logger.warning("recovered_jobs_on_startup count=%s", len(recovered))
        except Exception as exc:
            logger.error("startup_recovery_failed: %s", exc)
        self._stopping.clear()
        self._task = asyncio.create_task(self._run(), name="job-worker-loop")
        self._started = True
        await self._write_heartbeat(WorkerStatus.IDLE)
        logger.info("worker_started worker_id=%s", self.worker_id)

    async def stop(self, *, timeout: float = 30.0) -> None:
        """Graceful shutdown: finish the current safe step, then exit."""
        if not self._started:
            return
        logger.info("worker_stopping worker_id=%s", self.worker_id)
        await self._write_heartbeat(WorkerStatus.STOPPING)
        self._stopping.set()
        if self._task is not None:
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self._task, timeout=timeout)
            if not self._task.done():
                self._task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._task
        self._started = False
        await self._write_heartbeat(WorkerStatus.STOPPED)
        logger.info("worker_stopped worker_id=%s", self.worker_id)

    @property
    def is_running(self) -> bool:
        return self._started and self._task is not None and not self._task.done()

    # ----------------------------------------------------------------- main loop
    async def _run(self) -> None:
        """Poll forever: claim one job, process it fully, then poll again.

        A transient database outage must not kill the loop (that would silently
        stop all processing), so each iteration is isolated: the failure is
        logged once in detail, then with a concise line, and the loop backs off
        exponentially up to ``worker_error_backoff_max_seconds``.
        """
        failure_streak = 0
        try:
            while not self._stopping.is_set():
                try:
                    await self._maybe_recover()

                    job = await self._claim_next_job()
                    if job is None:
                        await self._write_heartbeat(WorkerStatus.IDLE)
                        failure_streak = 0
                        await self._sleep(self.poll_interval_seconds)
                        continue

                    self._current_job_id = job
                    set_log_context(job_id=str(job), worker_id=self.worker_id)
                    try:
                        await self._process(job)
                    finally:
                        self._current_job_id = None
                        self._current_stage = None
                        clear_log_context()
                        await self._write_heartbeat(WorkerStatus.IDLE)
                    failure_streak = 0
                except asyncio.CancelledError:  # pragma: no cover - shutdown path
                    raise
                except Exception as exc:
                    failure_streak += 1
                    delay = self._error_backoff_delay(failure_streak)
                    if failure_streak == 1:
                        logger.error(
                            "worker_iteration_failed error=%s retrying_in=%.1fs",
                            str(exc)[:300],
                            delay,
                            exc_info=True,
                        )
                    else:
                        logger.warning(
                            "worker_iteration_failed error=%s consecutive_failures=%s retrying_in=%.1fs",
                            str(exc)[:200],
                            failure_streak,
                            delay,
                        )
                    await self._write_heartbeat(WorkerStatus.ERROR)
                    await self._sleep(delay)
        except asyncio.CancelledError:  # pragma: no cover - shutdown path
            raise
        except Exception as exc:  # pragma: no cover - defensive: never leak out
            logger.critical("worker_loop_stopped_unexpectedly error=%s", str(exc)[:300], exc_info=True)

    def _error_backoff_delay(self, failure_streak: int) -> float:
        """Exponential backoff for transient failures (1s, 2s, 4s ... capped)."""
        base = settings.worker_error_backoff_seconds
        ceiling = settings.worker_error_backoff_max_seconds
        return min(ceiling, base * (2 ** (failure_streak - 1)))

    async def _claim_next_job(self) -> uuid.UUID | None:
        """Short transaction: claim, commit, then do long external work."""
        async with session_scope() as session:
            job = await JobRepository(session).claim_next()
            if job is None:
                return None
            logger.info("job_claimed job_id=%s filename=%s", job.id, job.original_filename)
            self._current_stage = job.stage
            return job.id

    async def _process(self, job_id: uuid.UUID) -> None:
        await self._write_heartbeat(WorkerStatus.BUSY, current_stage=JobStatus.VALIDATING.value)
        try:
            result = await self.orchestrator.process_job(job_id)
            logger.info("job_finished job_id=%s status=%s", job_id, result.status)
        except Exception as exc:
            logger.error("job_processing_error job_id=%s error=%s", job_id, exc, exc_info=True)

    # ---------------------------------------------------------------- heartbeat
    async def _write_heartbeat(
        self,
        status: WorkerStatus,
        *,
        current_stage: str | None = None,
    ) -> None:
        try:
            async with session_scope() as session:
                await WorkerStateRepository(session).heartbeat(
                    worker_id=self.worker_id,
                    status=status.value,
                    current_job_id=self._current_job_id,
                    current_stage=current_stage or self._current_stage,
                )
        except Exception as exc:
            logger.warning("worker_heartbeat_failed error=%s", str(exc)[:200])

    async def _maybe_recover(self) -> None:
        now = utcnow().timestamp()
        if now - self._last_recovery_at < self.recovery_interval_seconds:
            return
        self._last_recovery_at = now
        try:
            await recover_stale_jobs()
        except Exception as exc:
            logger.warning("periodic_recovery_failed error=%s", str(exc)[:200])

    async def _sleep(self, seconds: float) -> None:
        """Interruptible sleep so shutdown does not wait for the poll interval."""
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(self._stopping.wait(), timeout=seconds)


__all__ = ["WorkerLoop", "get_worker", "start_worker", "stop_worker"]

_worker: WorkerLoop | None = None


async def get_worker() -> WorkerLoop:
    global _worker
    if _worker is None:
        from app.worker.dispatcher import get_orchestrator

        _worker = WorkerLoop(orchestrator=await get_orchestrator())
    return _worker


async def start_worker() -> WorkerLoop:
    worker = await get_worker()
    await worker.start()
    return worker


async def stop_worker() -> None:
    global _worker
    if _worker is not None:
        await _worker.stop()
        _worker = None
