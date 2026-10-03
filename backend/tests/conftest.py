"""Shared test fixtures.

Design goals:
* the unit suite must run without PostgreSQL, FFmpeg or a Gemini API key;
* database/FFmpeg/AI-dependent suites skip automatically when unavailable, so
  ``pytest`` is always green in a fresh checkout and fully green in a complete
  environment.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio

from app.core.config import Settings, settings
from app.services.ai.rate_limiter import GeminiRateLimiter


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "integration: requires PostgreSQL")
    config.addinivalue_line("markers", "e2e: requires FFmpeg (and optionally PostgreSQL)")


def postgres_available() -> bool:
    """Best-effort synchronous check for a reachable PostgreSQL server."""
    if os.environ.get("SKIP_DB_TESTS", "").lower() in {"1", "true", "yes"}:
        return False
    import socket

    from sqlalchemy.engine import make_url

    try:
        url = make_url(settings.database_url)
    except Exception:  # pragma: no cover - malformed URL
        return False
    host = url.host or "localhost"
    port = url.port or 5432
    try:
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except OSError:
        return False


def ffmpeg_available() -> bool:
    return shutil.which(settings.ffmpeg_binary) is not None and (
        shutil.which(settings.ffprobe_binary) is not None
    )


@pytest.fixture(scope="session")
def db_available() -> bool:
    return postgres_available()


@pytest.fixture(scope="session")
def media_tools_available() -> bool:
    return ffmpeg_available()


@pytest_asyncio.fixture(autouse=True)
async def _engine_per_test() -> AsyncIterator[None]:
    """Dispose the application engine around every test.

    pytest-asyncio runs each test in a fresh event loop, while the application
    engine caches connections bound to the loop that created them. Without this,
    a pooled connection from a finished test would be reused on a closed loop
    (``RuntimeError: Event loop is closed`` during teardown). Production keeps a
    single loop forever, so this is a test-only concern.
    """
    from app.db.session import dispose_engine

    await dispose_engine()
    try:
        yield
    finally:
        await dispose_engine()


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    """Isolated DATA_DIR for tests that touch storage."""
    directory = tmp_path / "data"
    (directory / "jobs").mkdir(parents=True)
    (directory / "uploads").mkdir(parents=True)
    return directory


@pytest.fixture
def test_settings(tmp_data_dir: Path) -> Settings:
    """Settings override used by storage/service tests."""
    return Settings(
        app_env="test",
        ai_provider="mock",
        data_dir=tmp_data_dir,
        gemini_api_key="",
        chunk_duration_seconds=3600,
        chunk_overlap_seconds=60,
    )


@pytest.fixture
def fake_clock():
    """Deterministic clock: no real sleeping in tests."""
    from tests.fakes import FakeClock

    return FakeClock()


@pytest.fixture
def fake_history():
    """In-memory request history so the limiter needs no database."""
    from tests.fakes import FakeHistory

    return FakeHistory()


@pytest.fixture
def fast_limiter(fake_clock, fake_history) -> GeminiRateLimiter:
    """Rate limiter with a 60 s interval and in-memory history."""
    return GeminiRateLimiter(
        history=fake_history,
        clock=fake_clock,
        min_interval_seconds=60.0,
        rpm_limit=15,
        tpm_limit=250_000,
        rpd_limit=500,
    )


@pytest.fixture
def job_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture(scope="session")
def event_loop_policy():  # pragma: no cover - pytest-asyncio hook
    return asyncio.get_event_loop_policy()
