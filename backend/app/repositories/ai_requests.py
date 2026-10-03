"""AIRequestLog persistence and rolling-window quota queries.

The rate limiter reads this table so pacing survives a backend restart.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import AIRequestStatus
from app.core.timeutils import utcnow
from app.models.ai_request_log import AIRequestLog


class AIRequestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ----------------------------------------------------------------- writes
    async def start(
        self,
        *,
        job_id: uuid.UUID | None,
        model: str,
        phase: str,
        attempt_number: int,
        estimated_input_tokens: int | None,
        audio_chunk_id: uuid.UUID | None = None,
    ) -> AIRequestLog:
        record = AIRequestLog(
            job_id=job_id,
            audio_chunk_id=audio_chunk_id,
            phase=phase,
            model=model,
            attempt_number=attempt_number,
            started_at=utcnow(),
            estimated_input_tokens=estimated_input_tokens,
            status=AIRequestStatus.PENDING.value,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def finish_success(
        self,
        record_id: uuid.UUID,
        *,
        input_tokens: int | None,
        output_tokens: int | None,
        total_tokens: int | None,
        thinking_tokens: int | None = None,
        latency_ms: float | None = None,
    ) -> None:
        await self._finish(
            record_id,
            status=AIRequestStatus.SUCCESS.value,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            thinking_tokens=thinking_tokens,
            latency_ms=latency_ms,
        )

    async def finish_failure(
        self,
        record_id: uuid.UUID,
        *,
        status: str,
        error_code: str | None,
        error_message: str | None,
        http_status_code: int | None = None,
        latency_ms: float | None = None,
    ) -> None:
        await self._finish(
            record_id,
            status=status,
            error_code=error_code,
            error_message=error_message,
            http_status_code=http_status_code,
            latency_ms=latency_ms,
        )

    async def _finish(self, record_id: uuid.UUID, **values: Any) -> None:
        record = await self.session.get(AIRequestLog, record_id)
        if record is None:
            return
        record.completed_at = utcnow()
        for key, value in values.items():
            if value is not None:
                setattr(record, key, value)
        await self.session.flush()

    # ------------------------------------------------------------ rate limits
    async def last_request_start(self) -> datetime | None:
        return await self.session.scalar(select(func.max(AIRequestLog.started_at)))

    async def requests_since(self, since: datetime) -> int:
        """Every attempt counts, including retries (no hidden usage)."""
        count = await self.session.scalar(
            select(func.count()).select_from(AIRequestLog).where(AIRequestLog.started_at >= since)
        )
        return int(count or 0)

    async def tokens_since(self, since: datetime) -> int:
        row = await self.session.scalar(
            select(
                func.coalesce(
                    func.sum(
                        func.coalesce(
                            AIRequestLog.actual_total_tokens,
                            AIRequestLog.estimated_input_tokens,
                            0,
                        )
                    ),
                    0,
                )
            ).where(AIRequestLog.started_at >= since, AIRequestLog.status != AIRequestStatus.PENDING.value)
        )
        return int(row or 0)

    async def rolling_minute_requests(self, *, seconds: int = 60) -> int:
        return await self.requests_since(utcnow() - timedelta(seconds=seconds))

    async def rolling_minute_tokens(self, *, seconds: int = 60) -> int:
        return await self.tokens_since(utcnow() - timedelta(seconds=seconds))

    async def requests_today(self) -> int:
        """Requests since 00:00 UTC - the budget the application itself tracks."""
        now = utcnow()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return await self.requests_since(start_of_day)

    async def retry_count_for_job(self, job_id: uuid.UUID) -> int:
        count = await self.session.scalar(
            select(func.count())
            .select_from(AIRequestLog)
            .where(AIRequestLog.job_id == job_id, AIRequestLog.attempt_number > 1)
        )
        return int(count or 0)

    async def request_count_for_job(self, job_id: uuid.UUID) -> int:
        count = await self.session.scalar(
            select(func.count()).select_from(AIRequestLog).where(AIRequestLog.job_id == job_id)
        )
        return int(count or 0)

    async def recent(self, *, limit: int = 50) -> list[AIRequestLog]:
        stmt = select(AIRequestLog).order_by(AIRequestLog.started_at.desc()).limit(limit)
        return list((await self.session.execute(stmt)).scalars().all())

    async def phase_breakdown(self, *, since: datetime | None = None) -> dict[str, int]:
        stmt = select(AIRequestLog.phase, func.count()).group_by(AIRequestLog.phase)
        if since is not None:
            stmt = stmt.where(AIRequestLog.started_at >= since)
        rows = (await self.session.execute(stmt)).all()
        return {phase: int(count) for phase, count in rows}
