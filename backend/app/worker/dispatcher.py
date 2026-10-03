"""Builds and shares the AI client, rate limiter and orchestrator.

The rate limiter is a process-wide singleton so "one inference at a time" is
enforced across every code path (worker, API-triggered regeneration, CLI).
"""

from __future__ import annotations

import asyncio

from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import session_scope
from app.repositories.ai_requests import AIRequestRepository
from app.services.ai.client import GeminiClient, build_client
from app.services.ai.rate_limiter import GeminiRateLimiter
from app.services.jobs.orchestrator import JobOrchestrator
from app.services.storage import StorageService

logger = get_logger(__name__)

_client: GeminiClient | None = None
_limiter: GeminiRateLimiter | None = None
_lock = asyncio.Lock()


class RepositoryHistory:
    """History adapter so the limiter reads persisted request metadata.

    This is what makes pacing restart-safe: after a backend restart the limiter
    sees the most recent request start time from PostgreSQL.
    """

    async def last_request_start(self):
        async with session_scope() as session:
            return await AIRequestRepository(session).last_request_start()

    async def requests_since(self, since) -> int:
        async with session_scope() as session:
            return await AIRequestRepository(session).requests_since(since)

    async def tokens_since(self, since) -> int:
        async with session_scope() as session:
            return await AIRequestRepository(session).tokens_since(since)


async def get_client() -> GeminiClient:
    global _client
    async with _lock:
        if _client is None:
            _client = build_client()
    return _client


async def get_limiter() -> GeminiRateLimiter:
    global _limiter
    async with _lock:
        if _limiter is None:
            _limiter = GeminiRateLimiter(history=RepositoryHistory())
    return _limiter


def get_storage() -> StorageService:
    return StorageService()


async def get_orchestrator() -> JobOrchestrator:
    return JobOrchestrator(
        client=await get_client(),
        limiter=await get_limiter(),
        storage=get_storage(),
    )


async def reset_ai_runtime() -> None:
    """Reset cached AI singletons (used on shutdown and by tests)."""
    global _client, _limiter
    _client = None
    _limiter = None
    logger.debug("ai_runtime_reset provider=%s", settings.ai_provider)
