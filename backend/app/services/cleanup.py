"""Maintenance: stale upload cleanup and orphan detection.

Safety first: active jobs' source files, extracted audio and chunks are never
touched. Only clearly abandoned artifacts are removed.
"""

from __future__ import annotations

import contextlib
import uuid
from typing import Any

from app.core.config import settings
from app.core.enums import UploadStatus
from app.core.logging import get_logger
from app.db.session import session_scope
from app.repositories.uploads import UploadRepository
from app.services.storage import StorageService

logger = get_logger(__name__)


class CleanupService:
    def __init__(self, *, storage: StorageService | None = None) -> None:
        self.storage = storage or StorageService()

    async def cleanup_stale_uploads(self, *, older_than_hours: int | None = None) -> dict[str, Any]:
        """Mark abandoned upload sessions ABORTED and delete their temp files."""
        hours = older_than_hours or settings.stale_upload_hours
        aborted = 0
        deleted_files = 0
        freed_bytes = 0
        details: list[dict[str, Any]] = []

        async with session_scope() as session:
            repo = UploadRepository(session)
            stale = await repo.stale_uploading_sessions(older_than_hours=hours)
            for upload in stale:
                await repo.mark_status(upload.id, UploadStatus.ABORTED)
                aborted += 1
                from pathlib import Path

                path = Path(upload.temporary_path)
                if path.exists():
                    try:
                        size = path.stat().st_size
                        path.unlink()
                        deleted_files += 1
                        freed_bytes += size
                    except OSError as exc:
                        logger.warning("stale_upload_delete_failed path=%s error=%s", path, exc)
                details.append(
                    {
                        "upload_id": str(upload.id),
                        "filename": upload.original_filename,
                        "received_size": upload.received_size,
                    }
                )

        # Remove now-empty upload directories.
        if self.storage.uploads_dir.exists():
            for directory in self.storage.uploads_dir.iterdir():
                if directory.is_dir() and not any(directory.iterdir()):
                    with contextlib.suppress(OSError):
                        directory.rmdir()

        return {
            "aborted_upload_sessions": aborted,
            "deleted_files": deleted_files,
            "freed_bytes": freed_bytes,
            "orphan_directories": [],
            "details": details,
        }

    async def find_orphan_directories(self) -> list[str]:
        """Job directories on disk with no matching Job row (reported, not deleted)."""
        from sqlalchemy import select

        from app.models.job import Job

        if not self.storage.jobs_dir.exists():
            return []

        async with session_scope() as session:
            rows = (await session.execute(select(Job.id))).scalars().all()
        known = {str(row) for row in rows}

        orphans: list[str] = []
        for directory in sorted(self.storage.jobs_dir.iterdir()):
            if not directory.is_dir():
                continue
            if directory.name not in known:
                orphans.append(directory.name)
        return orphans

    async def cleanup_job_temp_chunks(self, job_id: uuid.UUID) -> int:
        """Delete chunk files whose chunk row is in a non-completed state.

        Completed chunks are kept: they are small, and keeping them makes
        debugging and partial re-runs possible. Source video and extracted audio
        are never deleted by maintenance.
        """
        from sqlalchemy import select

        from app.models.audio_chunk import AudioChunk

        async with session_scope() as session:
            rows = (
                await session.execute(
                    select(AudioChunk.chunk_index, AudioChunk.status).where(AudioChunk.job_id == job_id)
                )
            ).all()
        removable = {int(index) for index, status in rows if status != "COMPLETED"}

        paths = self.storage.job_paths(job_id)
        if not paths.chunks_dir.exists():
            return 0

        removed = 0
        for path in paths.chunks_dir.iterdir():
            if not path.is_file():
                continue
            try:
                index = int(path.stem.split("-")[-1])
            except (ValueError, IndexError):
                continue
            if index not in removable:
                continue
            try:
                path.unlink(missing_ok=True)
                removed += 1
            except OSError as exc:  # pragma: no cover - environment specific
                logger.warning("chunk_cleanup_failed path=%s error=%s", path, exc)
        return removed
