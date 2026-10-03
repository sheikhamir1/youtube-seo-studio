"""Integration fixtures.

These tests need a real PostgreSQL database. They skip automatically when none
is reachable, so the default suite stays green on a machine without Docker:

    docker compose up -d postgres
    alembic upgrade head
    pytest tests/integration
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.config import settings
from app.db.session import session_scope
from tests.conftest import postgres_available

pytestmark = pytest.mark.integration


@pytest.fixture(scope="session")
def _require_db() -> None:
    if not postgres_available():
        pytest.skip("PostgreSQL is not reachable: start it with `docker compose up -d postgres`.")


@pytest.fixture(scope="session", autouse=True)
def _migrated(_require_db: None) -> None:
    """Apply Alembic migrations once (also verifies that the migration works)."""
    from alembic import command
    from alembic.config import Config

    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[2] / "alembic"))
    command.upgrade(config, "head")


@pytest_asyncio.fixture
async def client(_migrated: None) -> AsyncIterator[AsyncClient]:
    """ASGI client without the application lifespan (no worker during tests)."""
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http:
        yield http


@pytest_asyncio.fixture(autouse=True)
async def _cleanup_jobs(_engine_per_test: None, _migrated: None) -> AsyncIterator[None]:
    """Keep the database clean between integration tests."""
    yield
    try:
        async with session_scope() as session:
            await session.execute(text("DELETE FROM jobs"))
            await session.execute(text("DELETE FROM upload_sessions"))
            await session.execute(text("DELETE FROM prompt_templates WHERE is_default = false"))
    except Exception:  # pragma: no cover - database already gone
        pass


@pytest_asyncio.fixture
async def default_template(client: AsyncClient) -> dict:
    """Ensure the seeded default template exists and return it."""
    response = await client.get(f"{settings.api_v1_prefix}/prompt-templates")
    payload = response.json()["data"]["items"]
    if not payload:
        pytest.skip("No prompt templates found: run `python -m app.cli seed`.")
    return payload[0]


@pytest_asyncio.fixture
async def uploaded_file(client: AsyncClient, tmp_path: Path) -> dict:
    """Upload a small fake video through the resumable upload API."""
    prefix = settings.api_v1_prefix
    content = b"\x00" * (2 * 1024 * 1024)
    part_size = 1024 * 1024
    create = await client.post(
        f"{prefix}/uploads",
        json={
            "filename": "integration test video.mp4",
            "content_type": "video/mp4",
            "size_bytes": len(content),
            "chunk_size_bytes": part_size,
        },
    )
    assert create.status_code == 201, create.text
    upload = create.json()["data"]

    for part_number in range(upload["total_parts"]):
        start = part_number * part_size
        chunk = content[start : start + part_size]
        put = await client.put(
            f"{prefix}/uploads/{upload['id']}/parts/{part_number}",
            content=chunk,
            headers={"content-type": "application/octet-stream"},
        )
        assert put.status_code == 200, put.text

    complete = await client.post(f"{prefix}/uploads/{upload['id']}/complete")
    assert complete.status_code == 200, complete.text
    return complete.json()["data"]
