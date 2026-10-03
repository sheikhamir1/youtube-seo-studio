"""PromptTemplate persistence (Reduce-phase templates only)."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prompt_template import PromptTemplate


class PromptTemplateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_all(self) -> list[PromptTemplate]:
        stmt = select(PromptTemplate).order_by(PromptTemplate.name.asc())
        return list((await self.session.execute(stmt)).scalars().all())

    async def get(self, template_id: uuid.UUID) -> PromptTemplate | None:
        return await self.session.get(PromptTemplate, template_id)

    async def get_by_name(self, name: str) -> PromptTemplate | None:
        stmt = select(PromptTemplate).where(func.lower(PromptTemplate.name) == name.strip().lower())
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def create(self, **values: object) -> PromptTemplate:
        template = PromptTemplate(**values)  # type: ignore[arg-type]
        self.session.add(template)
        await self.session.flush()
        return template

    async def update(self, template: PromptTemplate, **values: object) -> PromptTemplate:
        for key, value in values.items():
            if value is not None:
                setattr(template, key, value)
        await self.session.flush()
        return template

    async def delete(self, template: PromptTemplate) -> None:
        await self.session.delete(template)
        await self.session.flush()

    async def get_default(self) -> PromptTemplate | None:
        stmt = select(PromptTemplate).where(PromptTemplate.is_default.is_(True)).limit(1)
        template = (await self.session.execute(stmt)).scalar_one_or_none()
        if template is None:
            templates = await self.list_all()
            return templates[0] if templates else None
        return template
