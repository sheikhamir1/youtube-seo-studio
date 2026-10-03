"""FastAPI application entrypoint.

Startup order: settings -> logging -> database -> seed -> worker -> API.
Shutdown order: stop worker gracefully -> dispose engine.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.core.responses import register_exception_handlers
from app.db.session import dispose_engine, session_scope
from app.services.media.ffmpeg_runner import binary_available
from app.templates.seed_data import seed_all
from app.worker.loop import start_worker, stop_worker

configure_logging(settings.log_level, json_logs=settings.app_env.startswith("production"))
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings.ensure_data_dirs()
    logger.info(
        "startup app=%s env=%s provider=%s model=%s data_dir=%s",
        settings.app_name,
        settings.app_env,
        settings.ai_provider,
        settings.gemini_model,
        settings.data_dir,
        settings.gemini_allowed_models,
    )
    if not binary_available(settings.ffmpeg_binary) or not binary_available(settings.ffprobe_binary):
        logger.warning(
            "ffmpeg_missing: FFmpeg/FFprobe were not found on PATH. "
            "Media processing will fail until they are installed."
        )
    if settings.ai_provider == "gemini" and not settings.gemini_api_key:
        logger.warning(
            "gemini_key_missing: GEMINI_API_KEY is not configured. New analyses will be rejected "
            "until it is set in .env."
        )

    # Seeding is idempotent: it never duplicates the default template.
    try:
        async with session_scope() as session:
            await seed_all(session)
    except Exception as exc:
        logger.error("seed_failed: %s", exc)

    worker = None
    try:
        worker = await start_worker()
    except Exception as exc:
        logger.error("worker_start_failed: %s", exc)

    try:
        yield
    finally:
        if worker is not None:
            await stop_worker()
        await dispose_engine()
        logger.info("shutdown complete")


app = FastAPI(
    title=settings.app_name,
    description=(
        "Local-first AI-powered YouTube SEO automation for long-form video. "
        "Audio is extracted locally with FFmpeg and only small extracted audio chunks are sent to Gemini."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.enable_docs else None,
    redoc_url="/redoc" if settings.enable_docs else None,
    openapi_url="/openapi.json" if settings.enable_docs else None,
)

# CORS is configured explicitly for the Vite dev server; production runs
# same-origin through Nginx, so no wildcard is ever needed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

register_exception_handlers(app)
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/")
async def root() -> JSONResponse:
    return JSONResponse(
        {
            "data": {
                "app": settings.app_name,
                "version": "1.0.0",
                "api": settings.api_v1_prefix,
                "docs": "/docs" if settings.enable_docs else None,
                "message": "YouTube SEO Studio API. The user interface is served by the frontend.",
            },
            "message": "OK",
            "error": None,
        }
    )
