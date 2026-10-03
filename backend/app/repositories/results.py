"""SEOResult persistence, including current-version switching."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.seo_result import SEOResult


class SEOResultRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_job(self, job_id: uuid.UUID) -> list[SEOResult]:
        stmt = select(SEOResult).where(SEOResult.job_id == job_id).order_by(SEOResult.version_number.desc())
        return list((await self.session.execute(stmt)).scalars().all())

    async def get(self, result_id: uuid.UUID) -> SEOResult | None:
        return await self.session.get(SEOResult, result_id)

    async def get_current(self, job_id: uuid.UUID) -> SEOResult | None:
        stmt = select(SEOResult).where(SEOResult.job_id == job_id, SEOResult.is_current.is_(True))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def next_version_number(self, job_id: uuid.UUID) -> int:
        current = await self.session.scalar(
            select(func.max(SEOResult.version_number)).where(SEOResult.job_id == job_id)
        )
        return int(current or 0) + 1

    async def create_version(self, **values: Any) -> SEOResult:
        """Create a new version and flip ``is_current`` in one transaction.

        Flipping the previous current row happens in the same flush so two
        current versions cannot exist at the same time.
        """
        job_id = values["job_id"]
        await self.session.execute(
            update(SEOResult).where(SEOResult.job_id == job_id).values(is_current=False)
        )
        result = SEOResult(**values)
        result.is_current = True
        self.session.add(result)
        await self.session.flush()
        return result

    async def set_current(self, job_id: uuid.UUID, result_id: uuid.UUID) -> SEOResult | None:
        """Restore an older version as current (newer versions are preserved)."""
        target = await self.get(result_id)
        if target is None or target.job_id != job_id:
            return None
        await self.session.execute(
            update(SEOResult).where(SEOResult.job_id == job_id).values(is_current=False)
        )
        await self.session.flush()
        target.is_current = True
        await self.session.flush()
        return target

    async def update_fields(self, result: SEOResult, **values: Any) -> SEOResult:
        for key, value in values.items():
            if value is not None:
                setattr(result, key, value)
        result.edited_by_user = True
        await self.session.flush()
        return result

    async def current_scores(self, job_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
        if not job_ids:
            return {}
        stmt = select(SEOResult.job_id, SEOResult.seo_score).where(
            SEOResult.job_id.in_(job_ids), SEOResult.is_current.is_(True)
        )
        rows = (await self.session.execute(stmt)).all()
        return {row[0]: int(row[1]) for row in rows}
