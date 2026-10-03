"""UploadService: resumable chunked uploads streamed straight to disk."""

from __future__ import annotations

import asyncio
import contextlib
import os
import uuid
from pathlib import Path
from typing import Any, BinaryIO

from app.core.config import settings
from app.core.enums import UploadStatus
from app.core.errors import (
    AppError,
    DiskFullError,
    ErrorCode,
    StorageError,
    UploadError,
    ValidationError,
)
from app.core.logging import get_logger
from app.core.security import assert_disk_space, sanitize_filename
from app.repositories.uploads import UploadRepository
from app.services.storage import StorageService

logger = get_logger(__name__)

COPY_BLOCK_SIZE = 1024 * 1024  # 1 MiB streaming blocks: never the whole video in RAM


class UploadService:
    def __init__(self, *, repo: UploadRepository, storage: StorageService) -> None:
        self.repo = repo
        self.storage = storage

    # --------------------------------------------------------------- creation
    async def create_session(
        self,
        *,
        filename: str,
        size_bytes: int,
        content_type: str | None,
        chunk_size_bytes: int,
    ) -> dict[str, Any]:
        if size_bytes <= 0:
            raise ValidationError("The uploaded file size must be greater than zero.")
        total_parts = self.total_parts_for(size_bytes=size_bytes, chunk_size_bytes=chunk_size_bytes)
        session_id = uuid.uuid4()
        temp_path = self.storage.upload_temp_path(session_id, filename)

        # Fail fast (with a clear message) when the local disk cannot hold the file.
        assert_disk_space(temp_path.parent, size_bytes)
        # Pre-allocate the target file so partial writes are always visible.
        with temp_path.open("wb") as handle:
            handle.truncate(size_bytes)

        session_row = await self.repo.create_session(
            id=session_id,
            original_filename=sanitize_filename(filename),
            content_type=content_type,
            expected_size=int(size_bytes),
            received_size=0,
            chunk_size=int(chunk_size_bytes),
            total_parts=total_parts,
            status=UploadStatus.UPLOADING.value,
            temporary_path=str(temp_path),
        )
        logger.info(
            "upload_session_created upload_id=%s size=%s parts=%s",
            session_row.id,
            size_bytes,
            total_parts,
        )
        return {
            "id": session_row.id,
            "original_filename": session_row.original_filename,
            "content_type": session_row.content_type,
            "expected_size": session_row.expected_size,
            "received_size": 0,
            "chunk_size": session_row.chunk_size,
            "total_parts": session_row.total_parts,
            "status": session_row.status,
            "created_at": session_row.created_at,
            "updated_at": session_row.updated_at,
            "completed_at": session_row.completed_at,
        }

    # ------------------------------------------------------------ part writing
    async def store_part(
        self,
        *,
        upload_id: uuid.UUID,
        part_number: int,
        stream: BinaryIO,
        content_length: int | None,
    ) -> dict[str, Any]:
        session_row = await self._require_session(upload_id)
        if session_row.status != UploadStatus.UPLOADING.value:
            raise UploadError(
                f"This upload session is {session_row.status} and cannot receive more parts.",
                code=ErrorCode.UPLOAD_ALREADY_COMPLETED,
                http_status=409,
            )

        total_parts = max(1, session_row.total_parts)
        if part_number < 0 or part_number >= total_parts:
            raise UploadError(
                f"Part number {part_number} is out of range (0..{total_parts - 1}).",
                code=ErrorCode.UPLOAD_PART_INVALID,
                http_status=400,
            )

        byte_offset = part_number * session_row.chunk_size
        # The final part is legitimately shorter than chunk_size.
        remaining = session_row.expected_size - byte_offset
        max_length = min(session_row.chunk_size, max(0, remaining))

        path = Path(session_row.temporary_path)
        written = 0
        try:
            with path.open("r+b") as handle:
                handle.seek(byte_offset)
                while True:
                    block = stream.read(COPY_BLOCK_SIZE)
                    if not block:
                        break
                    if max_length and written + len(block) > max_length:
                        # Truncate oversize parts instead of corrupting the layout.
                        block = block[: max_length - written]
                        if not block:
                            break
                    handle.write(block)
                    written += len(block)
                    if max_length and written >= max_length:
                        break
        except OSError as exc:
            raise self._storage_error(exc, path) from exc

        if written == 0:
            raise UploadError(
                "An empty upload part was received.",
                code=ErrorCode.UPLOAD_PART_INVALID,
                http_status=400,
            )
        if content_length is not None and content_length != written:
            logger.debug("upload_part_length_mismatch declared=%s written=%s", content_length, written)

        await self.repo.upsert_part(
            upload_id=upload_id,
            part_number=part_number,
            byte_offset=byte_offset,
            byte_size=written,
        )
        received = await self.repo.recompute_received_size(upload_id)

        return {
            "part_number": part_number,
            "byte_offset": byte_offset,
            "byte_size": written,
            "received_size": received,
            "expected_size": session_row.expected_size,
            "progress_percent": round((received / session_row.expected_size) * 100, 2)
            if session_row.expected_size
            else 0.0,
        }

    # ------------------------------------------------- async streaming variant
    async def store_part_from_async_stream(
        self,
        *,
        upload_id: uuid.UUID,
        part_number: int,
        stream,  # AsyncIterator[bytes] from the ASGI request
        content_length: int | None,
    ) -> dict[str, Any]:
        """Stream an HTTP body directly into the pre-allocated file at an offset.

        The upload body is written in fixed-size blocks, so a 20 GB video never
        has to fit in RAM and a refresh only costs one part.
        """
        session_row = await self._require_session(upload_id)
        if session_row.status != UploadStatus.UPLOADING.value:
            raise UploadError(
                f"This upload session is {session_row.status} and cannot receive more parts.",
                code=ErrorCode.UPLOAD_ALREADY_COMPLETED,
                http_status=409,
            )

        total_parts = max(1, session_row.total_parts)
        if part_number < 0 or part_number >= total_parts:
            raise UploadError(
                f"Part number {part_number} is out of range (0..{total_parts - 1}).",
                code=ErrorCode.UPLOAD_PART_INVALID,
                http_status=400,
            )

        byte_offset = part_number * session_row.chunk_size
        remaining = session_row.expected_size - byte_offset
        max_length = min(session_row.chunk_size, max(0, remaining))
        path = Path(session_row.temporary_path)

        written = 0
        try:
            with path.open("r+b") as handle:
                handle.seek(byte_offset)
                async for block in stream:
                    if not block:
                        continue
                    if max_length and written + len(block) > max_length:
                        block = block[: max_length - written]
                        if not block:
                            break
                    await asyncio.to_thread(handle.write, block)
                    written += len(block)
                    if max_length and written >= max_length:
                        break
                await asyncio.to_thread(handle.flush)
                await asyncio.to_thread(os.fsync, handle.fileno())
        except OSError as exc:
            raise self._storage_error(exc, path) from exc

        if written == 0:
            raise UploadError(
                "An empty upload part was received.",
                code=ErrorCode.UPLOAD_PART_INVALID,
                http_status=400,
            )

        await self.repo.upsert_part(
            upload_id=upload_id,
            part_number=part_number,
            byte_offset=byte_offset,
            byte_size=written,
        )
        received = await self.repo.recompute_received_size(upload_id)

        return {
            "part_number": part_number,
            "byte_offset": byte_offset,
            "byte_size": written,
            "received_size": received,
            "expected_size": session_row.expected_size,
            "progress_percent": round((received / session_row.expected_size) * 100, 2)
            if session_row.expected_size
            else 0.0,
        }

    # ------------------------------------------------------------------ status
    async def status(self, upload_id: uuid.UUID) -> dict[str, Any]:
        session_row = await self._require_session(upload_id)
        parts = await self.repo.list_parts(upload_id)
        received_parts = sorted(part.part_number for part in parts)
        next_missing = self.next_missing_part(
            total_parts=session_row.total_parts, received_parts=received_parts
        )
        return {
            "id": session_row.id,
            "original_filename": session_row.original_filename,
            "content_type": session_row.content_type,
            "expected_size": session_row.expected_size,
            "received_size": session_row.received_size,
            "chunk_size": session_row.chunk_size,
            "total_parts": session_row.total_parts,
            "status": session_row.status,
            "created_at": session_row.created_at,
            "updated_at": session_row.updated_at,
            "completed_at": session_row.completed_at,
            "received_parts": received_parts,
            "next_missing_part": next_missing,
            "progress_percent": round((session_row.received_size / session_row.expected_size) * 100, 2)
            if session_row.expected_size
            else 0.0,
        }

    # ---------------------------------------------------------------- complete
    async def complete(self, upload_id: uuid.UUID) -> dict[str, Any]:
        session_row = await self._require_session(upload_id)
        path = Path(session_row.temporary_path)

        if session_row.status == UploadStatus.COMPLETED.value and path.exists():
            return await self.status(upload_id)

        parts = await self.repo.list_parts(upload_id)
        received_parts = sorted(part.part_number for part in parts)

        missing = [number for number in range(session_row.total_parts) if number not in set(received_parts)]
        if missing:
            raise UploadError(
                f"The upload is incomplete: {len(missing)} part(s) are missing.",
                details={"missing_parts": missing[:20], "next_missing_part": missing[0]},
                code=ErrorCode.UPLOAD_INCOMPLETE,
                http_status=409,
            )

        if not path.exists():
            raise StorageError(
                "The uploaded file disappeared from disk before completion.",
                code=ErrorCode.UPLOAD_STORAGE_ERROR,
                http_status=410,
            )

        actual_size = path.stat().st_size
        if actual_size != session_row.expected_size:
            raise UploadError(
                "The uploaded size does not match the declared file size.",
                details={"expected": session_row.expected_size, "actual": actual_size},
                code=ErrorCode.UPLOAD_SIZE_MISMATCH,
                http_status=409,
            )

        # Verify the tail part sizes so a truncated final part is caught here.
        for part in parts:
            expected_part_size = min(
                session_row.chunk_size,
                max(0, session_row.expected_size - part.byte_offset),
            )
            if part.byte_size != expected_part_size:
                raise UploadError(
                    f"Part {part.part_number} has an unexpected size.",
                    details={
                        "part_number": part.part_number,
                        "expected_bytes": expected_part_size,
                        "actual_bytes": part.byte_size,
                    },
                    code=ErrorCode.UPLOAD_SIZE_MISMATCH,
                    http_status=409,
                )

        await self.repo.mark_completed(upload_id)
        logger.info("upload_completed upload_id=%s size=%s", upload_id, actual_size)
        return await self.status(upload_id)

    # ------------------------------------------------------------------ abort
    async def abort(self, upload_id: uuid.UUID) -> None:
        session_row = await self._require_session(upload_id)
        await self.repo.mark_status(upload_id, UploadStatus.ABORTED)
        path = Path(session_row.temporary_path)
        if path.exists():
            path.unlink(missing_ok=True)
        with contextlib.suppress(OSError):
            path.parent.rmdir()
        logger.info("upload_aborted upload_id=%s", upload_id)

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def total_parts_for(*, size_bytes: int, chunk_size_bytes: int) -> int:
        """Ceil division: the last part may be shorter than the chunk size."""
        if chunk_size_bytes <= 0:
            raise ValidationError("chunk_size_bytes must be greater than zero.")
        return int((size_bytes + chunk_size_bytes - 1) // chunk_size_bytes)

    @staticmethod
    def next_missing_part(*, total_parts: int, received_parts: list[int]) -> int | None:
        received = set(received_parts)
        for number in range(total_parts):
            if number not in received:
                return number
        return None

    async def _require_session(self, upload_id: uuid.UUID):
        session_row = await self.repo.get(upload_id)
        if session_row is None:
            raise UploadError(
                "The upload session was not found.",
                code=ErrorCode.UPLOAD_SESSION_NOT_FOUND,
                http_status=404,
            )
        return session_row

    @staticmethod
    def _storage_error(exc: OSError, path: Path) -> AppError:
        if exc.errno == 28 or getattr(exc, "winerror", None) == 112:  # ENOSPC
            return DiskFullError(
                details={"path": str(path), "os_error": "ENOSPC"},
            )
        if exc.errno == 13:  # EACCES
            return StorageError(
                "The application cannot write to the data directory (permission denied).",
                details={"path": str(path)},
                code=ErrorCode.STORAGE_PERMISSION_ERROR,
                http_status=500,
            )
        return StorageError(
            "A local storage error occurred while writing the upload.",
            details={"path": str(path), "error": str(exc)[:300]},
            code=ErrorCode.UPLOAD_STORAGE_ERROR,
            http_status=500,
        )


def upload_root() -> Path:  # pragma: no cover - convenience helper
    return settings.data_dir / "uploads"


def env_upload_part_size() -> int:  # pragma: no cover - convenience helper
    return settings.upload_part_size_mb * 1024 * 1024


__all__ = ["COPY_BLOCK_SIZE", "UploadService", "env_upload_part_size", "upload_root"]
