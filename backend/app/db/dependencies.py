"""FastAPI dependencies for database access."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session_factory


async def get_db() -> AsyncIterator[AsyncSession]:
    """Yield a request-scoped session: COMMIT on success, rollback on error.

    The commit is essential - without it every write endpoint would appear to
    succeed while its transaction was rolled back when the session closed.
    Long-running work never happens inside this scope: FFmpeg and Gemini calls
    run in the worker with their own short transactions.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
