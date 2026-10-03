"""Job persistence: queue claim, progress updates, recovery queries."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Select, and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ACTIVE_JOB_STATUSES, JobStatus
from app.core.timeutils import utcnow
from app.models.job import Job


class JobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------- creation
    async def create(self, **values: Any) -> Job:
        job = Job(**values)
        self.session.add(job)
        await self.session.flush()
        return job

    # ------------------------------------------------------------------ read
    async def get(self, job_id: uuid.UUID) -> Job | None:
        return await self.session.get(Job, job_id)

    async def find_by_client_request_id(self, client_request_id: str) -> Job | None:
        """Idempotency lookup so a double-clicked Start button creates one job."""
        stmt = (
            select(Job)
            .where(Job.pipeline_config["client_request_id"].astext == client_request_id)
            .order_by(Job.created_at.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_for_update(self, job_id: uuid.UUID) -> Job | None:
        stmt = select(Job).where(Job.id == job_id).with_for_update()
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_jobs(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        search: str | None = None,
        sort: str = "-created_at",
    ) -> tuple[list[Job], int]:
        stmt: Select = select(Job)
        status_filter = (status or "").upper()
        if status_filter and status_filter != "ALL":
            if status_filter == "PROCESSING":
                # "Processing" is a UI concept covering several running states.
                stmt = stmt.where(Job.status.in_(ACTIVE_JOB_STATUSES))
            else:
                stmt = stmt.where(Job.status == status_filter)
        if search:
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(Job.original_filename.ilike(pattern), Job.prompt_template_name_snapshot.ilike(pattern))
            )

        sort_map = {
            "created_at": Job.created_at.asc(),
            "-created_at": Job.created_at.desc(),
            "updated_at": Job.updated_at.asc(),
            "-updated_at": Job.updated_at.desc(),
            "filename": Job.original_filename.asc(),
            "-filename": Job.original_filename.desc(),
        }
        stmt = stmt.order_by(sort_map.get(sort, Job.created_at.desc()))

        total = await self.session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
        rows = (
            (await self.session.execute(stmt.offset((page - 1) * page_size).limit(page_size))).scalars().all()
        )
        return list(rows), int(total or 0)

    async def counts_by_status(self) -> dict[str, int]:
        rows = (await self.session.execute(select(Job.status, func.count()).group_by(Job.status))).all()
        return {status: int(count) for status, count in rows}

    async def next_queued(self) -> Job | None:
        """Queue order preview (oldest first)."""
        stmt = select(Job).where(Job.status == JobStatus.QUEUED.value).order_by(Job.created_at.asc()).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    # ------------------------------------------------------- queue claiming
    async def claim_next(self) -> Job | None:
        """Atomically claim the oldest queued job.

        Uses ``FOR UPDATE SKIP LOCKED`` even though a single worker runs, so the
        design stays correct if a second process is ever added.
        """
        stmt = (
            select(Job)
            .where(Job.status == JobStatus.QUEUED.value)
            .order_by(Job.created_at.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        job = (await self.session.execute(stmt)).scalar_one_or_none()
        if job is None:
            return None
        now = utcnow()
        job.status = JobStatus.VALIDATING.value
        job.started_at = job.started_at or now
        job.last_heartbeat_at = now
        job.attempt_count = job.attempt_count + 1
        await self.session.flush()
        return job

    # ------------------------------------------------------------ mutations
    async def update_fields(self, job_id: uuid.UUID, **values: Any) -> None:
        if not values:
            return
        values["updated_at"] = utcnow()
        await self.session.execute(update(Job).where(Job.id == job_id).values(**values))
        await self.session.flush()

    async def touch_heartbeat(self, job_id: uuid.UUID, *, stage: str | None = None) -> None:
        values: dict[str, Any] = {"last_heartbeat_at": utcnow(), "updated_at": utcnow()}
        if stage:
            values["stage"] = stage
        await self.session.execute(update(Job).where(Job.id == job_id).values(**values))

    async def request_cancel(self, job_id: uuid.UUID) -> Job | None:
        job = await self.get(job_id)
        if job is None:
            return None
        if job.status == JobStatus.QUEUED.value:
            # Nothing started yet: cancel immediately.
            job.cancel_requested = True
            job.status = JobStatus.CANCELED.value
        else:
            job.cancel_requested = True
            if job.status not in (
                JobStatus.COMPLETED.value,
                JobStatus.FAILED.value,
                JobStatus.CANCELED.value,
            ):
                job.status = JobStatus.CANCEL_REQUESTED.value
        job.updated_at = utcnow()
        await self.session.flush()
        return job

    async def requeue(self, job_id: uuid.UUID) -> None:
        """Re-queue a failed/canceled job with completed work preserved."""
        await self.update_fields(
            job_id,
            status=JobStatus.QUEUED.value,
            cancel_requested=False,
            current_error_code=None,
            current_error_message=None,
            failed_stage=None,
            failed_chunk_index=None,
            failed_at=None,
            completed_at=None,
        )

    async def stale_running_jobs(self, *, stale_seconds: int) -> list[Job]:
        """Jobs in a running state whose heartbeat is older than the threshold."""
        cutoff = utcnow() - timedelta(seconds=stale_seconds)
        stmt = select(Job).where(
            and_(
                Job.status.in_(ACTIVE_JOB_STATUSES),
                or_(Job.last_heartbeat_at.is_(None), Job.last_heartbeat_at < cutoff),
            )
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def delete(self, job: Job) -> None:
        await self.session.delete(job)
        await self.session.flush()

    async def heartbeat_age_seconds(self, job: Job) -> float | None:
        if job.last_heartbeat_at is None:
            return None
        delta: timedelta = utcnow() - job.last_heartbeat_at
        return delta.total_seconds()

    async def completed_since(self, since: datetime) -> list[Job]:
        stmt = select(Job).where(Job.status == JobStatus.COMPLETED.value, Job.completed_at >= since)
        return list((await self.session.execute(stmt)).scalars().all())
