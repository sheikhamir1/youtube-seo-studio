"""JobEvent persistence: sequence numbering for SSE and the log page."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import EventLevel
from app.models.job_event import JobEvent


class JobEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def append(
        self,
        *,
        job_id: uuid.UUID,
        event_type: str,
        message: str,
        level: str = EventLevel.INFO.value,
        stage: str | None = None,
        progress_percent: float | None = None,
        chunk_index: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> JobEvent:
        last_sequence = await self.session.scalar(
            select(func.coalesce(func.max(JobEvent.sequence_number), 0)).where(JobEvent.job_id == job_id)
        )
        event = JobEvent(
            job_id=job_id,
            sequence_number=int(last_sequence or 0) + 1,
            event_type=event_type,
            level=level,
            stage=stage,
            message=message,
            progress_percent=progress_percent,
            chunk_index=chunk_index,
            payload=payload,
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def list_for_job(
        self,
        job_id: uuid.UUID,
        *,
        limit: int = 200,
        offset: int = 0,
        level: str | None = None,
    ) -> tuple[list[JobEvent], int]:
        stmt = select(JobEvent).where(JobEvent.job_id == job_id)
        if level:
            stmt = stmt.where(JobEvent.level == level)
        total = await self.session.scalar(select(func.count()).select_from(stmt.subquery()))
        rows = (
            (
                await self.session.execute(
                    stmt.order_by(JobEvent.sequence_number.asc()).offset(offset).limit(limit)
                )
            )
            .scalars()
            .all()
        )
        return list(rows), int(total or 0)

    async def list_after(self, job_id: uuid.UUID, *, after_id: int, limit: int = 200) -> list[JobEvent]:
        """Events with ``id > after_id`` - used to honour SSE Last-Event-ID."""
        stmt = (
            select(JobEvent)
            .where(JobEvent.job_id == job_id, JobEvent.id > after_id)
            .order_by(JobEvent.id.asc())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def latest(self, job_id: uuid.UUID) -> JobEvent | None:
        stmt = select(JobEvent).where(JobEvent.job_id == job_id).order_by(JobEvent.id.desc()).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none()
