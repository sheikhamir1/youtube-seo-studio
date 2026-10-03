"""AppSettings persistence (single row, non-secret settings)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings as env_settings
from app.models.app_settings import AppSettings


class AppSettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create(self) -> AppSettings:
        record = await self.session.get(AppSettings, 1)
        if record is None:
            record = AppSettings(
                id=1,
                default_model=env_settings.gemini_model,
                allowed_models=[],
                gemini_rpm_limit=env_settings.gemini_rpm_limit,
                gemini_tpm_limit=env_settings.gemini_tpm_limit,
                gemini_rpd_limit=env_settings.gemini_rpd_limit,
                gemini_min_interval_seconds=env_settings.gemini_min_interval_seconds,
                chunk_duration_seconds=env_settings.chunk_duration_seconds,
                chunk_overlap_seconds=env_settings.chunk_overlap_seconds,
                map_max_topics_per_chunk=env_settings.map_max_topics_per_chunk,
                max_gemini_retries=env_settings.max_gemini_retries,
                max_schema_repair_attempts=env_settings.max_schema_repair_attempts,
                audio_format=env_settings.audio_format,
            )
            self.session.add(record)
            await self.session.flush()
        return record

    async def update(self, record: AppSettings, **values: object) -> AppSettings:
        for key, value in values.items():
            if value is not None:
                setattr(record, key, value)
        await self.session.flush()
        return record
