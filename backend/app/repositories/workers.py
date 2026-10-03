"""WorkerState heartbeat persistence."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import WorkerStatus
from app.core.timeutils import utcnow
from app.models.worker_state import WorkerState


class WorkerStateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, worker_id: str) -> WorkerState | None:
        stmt = select(WorkerState).where(WorkerState.worker_id == worker_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_first(self) -> WorkerState | None:
        stmt = select(WorkerState).order_by(WorkerState.updated_at.desc()).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def heartbeat(
        self,
        *,
        worker_id: str,
        status: str,
        current_job_id: uuid.UUID | None = None,
        current_stage: str | None = None,
    ) -> WorkerState:
        now = utcnow()
        record = await self.get(worker_id)
        if record is None:
            record = WorkerState(
                worker_id=worker_id,
                status=status,
                last_heartbeat_at=now,
                current_job_id=current_job_id,
                current_stage=current_stage,
                updated_at=now,
            )
            self.session.add(record)
        else:
            record.status = status
            record.last_heartbeat_at = now
            record.current_job_id = current_job_id
            record.current_stage = current_stage
            record.updated_at = now
        await self.session.flush()
        return record

    async def set_status(self, worker_id: str, status: WorkerStatus) -> None:
        await self.heartbeat(worker_id=worker_id, status=status.value)
