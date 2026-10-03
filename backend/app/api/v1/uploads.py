"""Resumable upload endpoints. Bodies are streamed to disk, never buffered."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import ErrorCode, UploadError
from app.core.responses import success
from app.db.dependencies import get_db
from app.repositories.uploads import UploadRepository
from app.schemas.upload import UploadCompleteRequest, UploadCreateRequest
from app.services.storage import StorageService
from app.services.uploads.service import UploadService

router = APIRouter(prefix="/uploads", tags=["uploads"])


def _service(db: AsyncSession) -> UploadService:
    return UploadService(repo=UploadRepository(db), storage=StorageService())


@router.post("", status_code=201)
async def create_upload(payload: UploadCreateRequest, db: AsyncSession = Depends(get_db)) -> dict:
    service = _service(db)
    data = await service.create_session(
        filename=payload.filename,
        size_bytes=payload.size_bytes,
        content_type=payload.content_type,
        chunk_size_bytes=payload.chunk_size_bytes,
    )
    return success(data, message="Upload session created.")


@router.get("/config/part-size")
async def part_size_config() -> dict:
    """The part size the browser should use (network request size only)."""
    return success(
        {
            "chunk_size_bytes": settings.upload_part_size_mb * 1024 * 1024,
            "note": "Upload part size is a network request size, not a total file-size limit.",
        }
    )


@router.get("/{upload_id}")
async def upload_status(upload_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    return success(await _service(db).status(upload_id))


@router.put("/{upload_id}/parts/{part_number}")
async def upload_part(
    upload_id: uuid.UUID,
    part_number: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Raw binary body streamed straight to the target file offset."""
    if part_number < 0:
        raise UploadError(
            "Part numbers must be zero or greater.",
            code=ErrorCode.UPLOAD_PART_INVALID,
            http_status=400,
        )
    declared = request.headers.get("content-length")
    content_length = int(declared) if declared and declared.isdigit() else None

    service = _service(db)
    # Starlette exposes the raw request body through ``request.stream()``; the
    # body is written block-by-block at the correct file offset.
    data = await service.store_part_from_async_stream(
        upload_id=upload_id,
        part_number=part_number,
        stream=request.stream(),
        content_length=content_length,
    )
    return success(data, message=f"Part {part_number} stored.")


@router.post("/{upload_id}/complete")
async def complete_upload(
    upload_id: uuid.UUID,
    payload: UploadCompleteRequest | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    data = await _service(db).complete(upload_id)
    if payload and payload.size_bytes and payload.size_bytes != data["received_size"]:
        raise UploadError(
            "The uploaded size does not match the size reported by the browser.",
            details={"expected": payload.size_bytes, "received": data["received_size"]},
            code=ErrorCode.UPLOAD_SIZE_MISMATCH,
            http_status=409,
        )
    return success(data, message="Upload complete and verified.")


@router.delete("/{upload_id}")
async def abort_upload(upload_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    await _service(db).abort(upload_id)
    return success({"id": str(upload_id)}, message="Upload aborted.")
