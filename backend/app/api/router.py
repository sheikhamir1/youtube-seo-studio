"""API v1 router aggregation."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import health, jobs, prompt_templates, results, system, uploads, youtube

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(system.router)
api_router.include_router(uploads.router)
api_router.include_router(jobs.router)
api_router.include_router(results.router)
api_router.include_router(prompt_templates.router)
api_router.include_router(youtube.router)
