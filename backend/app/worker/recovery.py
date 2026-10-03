"""Startup recovery for jobs interrupted by a crash or a backend restart.

Semantics are at-least-once: a request that was in flight when the process died
may be retried, because no successful result was persisted.
"""

from __future__ import annotations

from app.core.config import settings
from app.core.enums import EventLevel, JobEventType, JobStatus
from app.core.logging import get_logger
from app.core.timeutils import utcnow
from app.db.session import session_scope
from app.repositories.events import JobEventRepository
from app.repositories.jobs import JobRepository
from app.services.jobs.progress import compute_progress
from app.services.jobs.state import stage_for_status

logger = get_logger(__name__)


async def recover_stale_jobs(*, stale_seconds: int | None = None) -> list[str]:
    """Re-queue jobs whose worker heartbeat went stale. Completed work is kept."""
    threshold = stale_seconds or settings.worker_stale_seconds
    recovered: list[str] = []

    async with session_scope() as session:
        job_repo = JobRepository(session)
        event_repo = JobEventRepository(session)
        stale_jobs = await job_repo.stale_running_jobs(stale_seconds=threshold)

        for job in stale_jobs:
            if job.status == JobStatus.CANCEL_REQUESTED.value:
                job.status = JobStatus.CANCELED.value
                job.cancel_requested = True
                await event_repo.append(
                    job_id=job.id,
                    event_type=JobEventType.JOB_CANCELED.value,
                    level=EventLevel.WARNING.value,
                    stage=stage_for_status(job.status),
                    message="Job canceled during recovery (cancel was requested before shutdown).",
                )
                recovered.append(str(job.id))
                continue

            age = await job_repo.heartbeat_age_seconds(job)
            previous_stage = job.stage
            await job_repo.update_fields(
                job.id,
                status=JobStatus.QUEUED.value,
                stage=previous_stage or stage_for_status(job.status),
                progress_percent=min(
                    job.progress_percent or 0.0,
                    compute_progress(stage=previous_stage or "VALIDATION", stage_fraction=0.0),
                ),
                cancel_requested=False,
                last_heartbeat_at=utcnow(),
            )
            await event_repo.append(
                job_id=job.id,
                event_type=JobEventType.JOB_RECOVERED.value,
                level=EventLevel.WARNING.value,
                stage=previous_stage,
                message=(
                    "Worker heartbeat was stale, so the job was re-queued. "
                    "Completed chunks are preserved and processing resumes from the first "
                    "incomplete step."
                ),
                payload={
                    "heartbeat_age_seconds": age,
                    "stale_threshold_seconds": threshold,
                    "previous_status": job.status,
                },
            )
            recovered.append(str(job.id))
            logger.warning(
                "job_recovered job_id=%s previous_stage=%s heartbeat_age=%s",
                job.id,
                previous_stage,
                age,
            )

    return recovered
