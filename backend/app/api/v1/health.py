"""Health and readiness endpoints (used by Docker healthchecks)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.responses import success
from app.db.dependencies import get_db
from app.services.media.ffmpeg_runner import binary_available

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    """Liveness: the API process is up. No database dependency."""
    return success({"status": "ok", "app": settings.app_name, "env": settings.app_env})


@router.get("/ready")
async def ready(db: AsyncSession = Depends(get_db)) -> dict:
    """Readiness: dependencies the application needs in order to work."""
    database_ok = True
    detail = None
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        database_ok = False
        detail = exc.__class__.__name__

    ffmpeg_ok = binary_available(settings.ffmpeg_binary)
    ffprobe_ok = binary_available(settings.ffprobe_binary)
    ready_state = database_ok and ffmpeg_ok and ffprobe_ok

    return success(
        {
            "ready": ready_state,
            "database": {"ok": database_ok, "detail": detail},
            "ffmpeg": {"ok": ffmpeg_ok},
            "ffprobe": {"ok": ffprobe_ok},
            "gemini_key_configured": bool(settings.gemini_api_key) or settings.ai_provider == "mock",
        }
    )
