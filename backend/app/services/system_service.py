"""SystemService: status, quota, models and storage reporting for the UI."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.enums import ACTIVE_JOB_STATUSES, JobStatus
from app.core.security import disk_usage
from app.repositories.ai_requests import AIRequestRepository
from app.repositories.jobs import JobRepository
from app.repositories.workers import WorkerStateRepository
from app.services.ai.model_registry import all_models, configured_model_ids, default_model
from app.services.ai.usage import estimate_chunk_input_tokens
from app.services.media.ffmpeg_runner import binary_available
from app.services.prompts.defaults import MAP_SYSTEM_PROMPT
from app.services.storage import StorageService


class SystemService:
    def __init__(self, session: AsyncSession, *, storage: StorageService | None = None) -> None:
        self.session = session
        self.storage = storage or StorageService()

    # ------------------------------------------------------------------ status
    async def status(self) -> dict[str, Any]:
        database_ok, database_detail = await self._check_database()

        ffmpeg_ok = binary_available(settings.ffmpeg_binary)
        ffprobe_ok = binary_available(settings.ffprobe_binary)

        worker_payload: dict[str, Any] | None = None
        queued = 0
        active = 0

        if database_ok:
            worker_row = await WorkerStateRepository(self.session).get_first()
            counts = await JobRepository(self.session).counts_by_status()
            queued = counts.get(JobStatus.QUEUED.value, 0)
            active = sum(counts.get(status, 0) for status in ACTIVE_JOB_STATUSES)
            if worker_row is not None:
                from app.core.timeutils import utcnow

                age = (utcnow() - worker_row.last_heartbeat_at).total_seconds()
                worker_payload = {
                    "worker_id": worker_row.worker_id,
                    "status": worker_row.status,
                    "last_heartbeat_at": worker_row.last_heartbeat_at.isoformat(),
                    "heartbeat_age_seconds": round(age, 1),
                    "current_job_id": str(worker_row.current_job_id) if worker_row.current_job_id else None,
                    "current_stage": worker_row.current_stage,
                    "alive": age <= settings.worker_stale_seconds,
                }

        disk = None
        try:
            info = disk_usage(settings.data_dir)
            disk = {
                "path": info["path"],
                "total_bytes": info["total_bytes"],
                "used_bytes": info["used_bytes"],
                "free_bytes": info["free_bytes"],
                "used_percent": info["used_percent"],
            }
        except OSError:
            disk = None

        return {
            "app_env": settings.app_env,
            "app_name": settings.app_name,
            "database": {"ok": database_ok, "detail": database_detail},
            "ffmpeg": {
                "ok": ffmpeg_ok,
                "detail": "available" if ffmpeg_ok else "FFmpeg is not installed or not on PATH.",
            },
            "ffprobe": {
                "ok": ffprobe_ok,
                "detail": "available" if ffprobe_ok else "FFprobe is not installed or not on PATH.",
            },
            # The API key itself is never returned - only whether it is configured.
            "gemini_key_configured": bool(settings.gemini_api_key) or settings.ai_provider == "mock",
            "ai_provider": settings.ai_provider,
            "default_model": default_model(),
            "worker": worker_payload,
            "data_dir": str(settings.data_dir),
            "disk": disk,
            "queued_jobs": queued,
            "active_jobs": active,
        }

    async def models(self) -> dict[str, Any]:
        default = default_model()
        return {
            "models": [
                profile.to_dict(is_default=profile.id == default, is_configured=is_configured)
                for profile, is_configured in all_models()
            ],
            "default_model": default,
            "selectable_models": configured_model_ids(),
        }

    # ------------------------------------------------------------------- quota
    async def quota(self) -> dict[str, Any]:
        repo = AIRequestRepository(self.session)
        requests_today = await repo.requests_today()
        rolling_requests = await repo.rolling_minute_requests()
        rolling_tokens = await repo.rolling_minute_tokens()

        # Estimate the next Map request cost from a nominal chunk.
        estimated_next = estimate_chunk_input_tokens(
            settings.chunk_duration_seconds, system_prompt=MAP_SYSTEM_PROMPT
        )

        warning = None
        if settings.gemini_min_interval_seconds < 60:
            warning = "Less conservative than the default free-tier pacing."
        if settings.gemini_rpd_limit and requests_today >= settings.gemini_rpd_limit:
            warning = "The configured daily application budget has been reached."

        return {
            "label": "Application-tracked usage",
            "requests_today": requests_today,
            "rpd_limit": settings.gemini_rpd_limit,
            "rolling_minute_requests": rolling_requests,
            "rpm_limit": settings.gemini_rpm_limit,
            "rolling_minute_tokens": rolling_tokens,
            "tpm_limit": settings.gemini_tpm_limit,
            "min_interval_seconds": settings.gemini_min_interval_seconds,
            "estimated_next_request_tokens": estimated_next,
            "daily_budget_reached": bool(
                settings.gemini_rpd_limit and requests_today >= settings.gemini_rpd_limit
            ),
            "warning": warning,
        }

    async def storage_usage(self) -> dict[str, Any]:
        return self.storage.storage_usage()

    # --------------------------------------------------------------- internals
    async def _check_database(self) -> tuple[bool, str | None]:
        try:
            await self.session.execute(text("SELECT 1"))
            return True, None
        except Exception as exc:
            return False, exc.__class__.__name__
