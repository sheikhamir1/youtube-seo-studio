"""Upload session / part persistence."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import UploadStatus
from app.core.timeutils import utcnow
from app.models.upload import UploadPart, UploadSession


class UploadRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_session(self, **values: Any) -> UploadSession:
        session_row = UploadSession(**values)
        self.session.add(session_row)
        await self.session.flush()
        return session_row

    async def get(self, upload_id: uuid.UUID) -> UploadSession | None:
        return await self.session.get(UploadSession, upload_id)

    async def get_with_parts(self, upload_id: uuid.UUID) -> UploadSession | None:
        stmt = select(UploadSession).where(UploadSession.id == upload_id)
        session_row = (await self.session.execute(stmt)).scalar_one_or_none()
        if session_row is not None:
            await self.session.refresh(session_row, attribute_names=["parts"])
        return session_row

    async def list_parts(self, upload_id: uuid.UUID) -> list[UploadPart]:
        stmt = (
            select(UploadPart)
            .where(UploadPart.upload_session_id == upload_id)
            .order_by(UploadPart.part_number.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_part(self, upload_id: uuid.UUID, part_number: int) -> UploadPart | None:
        stmt = select(UploadPart).where(
            UploadPart.upload_session_id == upload_id, UploadPart.part_number == part_number
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def upsert_part(
        self,
        *,
        upload_id: uuid.UUID,
        part_number: int,
        byte_offset: int,
        byte_size: int,
    ) -> UploadPart:
        """Record a part; re-uploading the same part number updates it (idempotent)."""
        part = await self.get_part(upload_id, part_number)
        if part is None:
            part = UploadPart(
                upload_session_id=upload_id,
                part_number=part_number,
                byte_offset=byte_offset,
                byte_size=byte_size,
            )
            self.session.add(part)
        else:
            part.byte_offset = byte_offset
            part.byte_size = byte_size
            part.received_at = utcnow()
        await self.session.flush()
        return part

    async def recompute_received_size(self, upload_id: uuid.UUID) -> int:
        total = await self.session.scalar(
            select(func.coalesce(func.sum(UploadPart.byte_size), 0)).where(
                UploadPart.upload_session_id == upload_id
            )
        )
        session_row = await self.get(upload_id)
        if session_row is not None:
            session_row.received_size = int(total or 0)
            session_row.updated_at = utcnow()
            await self.session.flush()
        return int(total or 0)

    async def mark_completed(self, upload_id: uuid.UUID, *, temporary_path: str | None = None) -> None:
        session_row = await self.get(upload_id)
        if session_row is None:
            return
        session_row.status = UploadStatus.COMPLETED.value
        session_row.completed_at = utcnow()
        session_row.updated_at = utcnow()
        if temporary_path:
            session_row.temporary_path = temporary_path
        await self.session.flush()

    async def mark_status(self, upload_id: uuid.UUID, status: UploadStatus) -> None:
        session_row = await self.get(upload_id)
        if session_row is not None:
            session_row.status = status.value
            session_row.updated_at = utcnow()
            await self.session.flush()

    async def stale_uploading_sessions(self, *, older_than_hours: int) -> list[UploadSession]:
        cutoff = utcnow() - timedelta(hours=older_than_hours)
        stmt = select(UploadSession).where(
            UploadSession.status == UploadStatus.UPLOADING.value,
            UploadSession.updated_at < cutoff,
        )
        return list((await self.session.execute(stmt)).scalars().all())
