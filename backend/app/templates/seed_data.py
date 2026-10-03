"""Idempotent seeding of prompt templates and the app settings row."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.repositories.prompt_templates import PromptTemplateRepository
from app.repositories.settings import AppSettingsRepository
from app.services.prompts.defaults import SEED_TEMPLATES

logger = get_logger(__name__)


async def seed_prompt_templates(session: AsyncSession) -> dict[str, int]:
    """Create the seeded templates only when they are missing.

    Re-running this never creates duplicates, so it is safe to call on every
    startup and from the CLI.
    """
    repo = PromptTemplateRepository(session)
    created = 0
    existing = 0

    for template in SEED_TEMPLATES:
        name = str(template["name"])
        if await repo.get_by_name(name) is not None:
            existing += 1
            continue
        await repo.create(
            name=name,
            description=template.get("description"),
            system_prompt=template["system_prompt"],
            user_prompt_template=template["user_prompt_template"],
            is_default=bool(template.get("is_default", False)),
        )
        created += 1

    # Guarantee exactly one default template exists.
    default = await repo.get_default()
    if default is not None and not default.is_default:
        default.is_default = True
        await session.flush()

    return {"created": created, "existing": existing}


async def ensure_app_settings(session: AsyncSession) -> None:
    await AppSettingsRepository(session).get_or_create()


async def seed_all(session: AsyncSession) -> dict[str, int]:
    result = await seed_prompt_templates(session)
    await ensure_app_settings(session)
    logger.info(
        "seed_complete templates_created=%s templates_existing=%s",
        result["created"],
        result["existing"],
    )
    return result
