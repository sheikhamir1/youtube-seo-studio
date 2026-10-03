"""AudioChunk persistence."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ChunkStatus
from app.core.timeutils import utcnow
from app.models.audio_chunk import AudioChunk


class ChunkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def bulk_create(self, chunks: list[dict[str, Any]]) -> list[AudioChunk]:
        rows = [AudioChunk(**chunk) for chunk in chunks]
        self.session.add_all(rows)
        await self.session.flush()
        return rows

    async def list_for_job(self, job_id: uuid.UUID) -> list[AudioChunk]:
        stmt = select(AudioChunk).where(AudioChunk.job_id == job_id).order_by(AudioChunk.chunk_index.asc())
        return list((await self.session.execute(stmt)).scalars().all())

    async def get(self, chunk_id: uuid.UUID) -> AudioChunk | None:
        return await self.session.get(AudioChunk, chunk_id)

    async def get_by_index(self, job_id: uuid.UUID, chunk_index: int) -> AudioChunk | None:
        stmt = select(AudioChunk).where(AudioChunk.job_id == job_id, AudioChunk.chunk_index == chunk_index)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def count_by_status(self, job_id: uuid.UUID) -> dict[str, int]:
        rows = (
            await self.session.execute(
                select(AudioChunk.status, func.count())
                .where(AudioChunk.job_id == job_id)
                .group_by(AudioChunk.status)
            )
        ).all()
        return {status: int(count) for status, count in rows}

    async def mark_processing(self, chunk_id: uuid.UUID) -> None:
        await self.session.execute(
            update(AudioChunk)
            .where(AudioChunk.id == chunk_id)
            .values(
                status=ChunkStatus.PROCESSING.value,
                started_at=utcnow(),
                attempt_count=AudioChunk.attempt_count + 1,
                error_code=None,
                error_message=None,
            )
        )
        await self.session.flush()

    async def mark_completed(
        self,
        chunk_id: uuid.UUID,
        *,
        relative_result: dict[str, Any],
        normalized_result: dict[str, Any],
        actual_input_tokens: int | None,
        actual_output_tokens: int | None,
        gemini_file_name: str | None,
        gemini_file_uri: str | None,
    ) -> None:
        await self.session.execute(
            update(AudioChunk)
            .where(AudioChunk.id == chunk_id)
            .values(
                status=ChunkStatus.COMPLETED.value,
                relative_result=relative_result,
                normalized_result=normalized_result,
                actual_input_tokens=actual_input_tokens,
                actual_output_tokens=actual_output_tokens,
                gemini_file_name=gemini_file_name,
                gemini_file_uri=gemini_file_uri,
                completed_at=utcnow(),
                error_code=None,
                error_message=None,
            )
        )
        await self.session.flush()

    async def mark_failed(self, chunk_id: uuid.UUID, *, code: str, message: str) -> None:
        await self.session.execute(
            update(AudioChunk)
            .where(AudioChunk.id == chunk_id)
            .values(status=ChunkStatus.FAILED.value, error_code=code, error_message=message)
        )
        await self.session.flush()

    async def mark_file_cleaned(self, chunk_id: uuid.UUID) -> None:
        await self.session.execute(
            update(AudioChunk).where(AudioChunk.id == chunk_id).values(gemini_file_cleaned=True)
        )
        await self.session.flush()

    async def reset_incomplete(self, job_id: uuid.UUID) -> int:
        """Reset PROCESSING/FAILED chunks to PENDING for a retry attempt."""
        result = await self.session.execute(
            update(AudioChunk)
            .where(
                AudioChunk.job_id == job_id,
                AudioChunk.status.in_([ChunkStatus.PROCESSING.value, ChunkStatus.FAILED.value]),
            )
            .values(status=ChunkStatus.PENDING.value, error_code=None, error_message=None)
        )
        await self.session.flush()
        return int(result.rowcount or 0)

    async def delete_for_job(self, job_id: uuid.UUID) -> None:
        await self.session.execute(delete(AudioChunk).where(AudioChunk.job_id == job_id))
        await self.session.flush()

    async def token_totals(self, job_id: uuid.UUID) -> tuple[int, int]:
        row = (
            await self.session.execute(
                select(
                    func.coalesce(func.sum(AudioChunk.actual_input_tokens), 0),
                    func.coalesce(func.sum(AudioChunk.actual_output_tokens), 0),
                ).where(AudioChunk.job_id == job_id)
            )
        ).one()
        return int(row[0] or 0), int(row[1] or 0)
