"""Upload schemas (resumable upload flow)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel

DEFAULT_PART_SIZE_BYTES = 32 * 1024 * 1024


class UploadCreateRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=400)
    content_type: str | None = Field(default=None, max_length=160)
    size_bytes: int = Field(gt=0, description="Total file size in bytes")
    chunk_size_bytes: int = Field(
        default=DEFAULT_PART_SIZE_BYTES,
        ge=64 * 1024,
        le=512 * 1024 * 1024,
        description="Browser upload part size (network request size, not a file limit)",
    )


class UploadSessionRead(ORMModel):
    id: uuid.UUID
    original_filename: str
    content_type: str | None
    expected_size: int
    received_size: int
    chunk_size: int
    total_parts: int
    status: str
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class UploadStatusRead(UploadSessionRead):
    """Resume payload - exactly what the browser needs to continue."""

    received_parts: list[int] = Field(default_factory=list)
    next_missing_part: int | None = None
    progress_percent: float = 0.0


class UploadPartRead(BaseModel):
    part_number: int
    byte_offset: int
    byte_size: int
    received_at: datetime

    @field_validator("byte_size")
    @classmethod
    def _positive(cls, value: int) -> int:
        if value < 0:
            raise ValueError("byte_size must be >= 0")
        return value


class UploadCompleteRequest(BaseModel):
    """Optional client-side sanity values; the backend verifies them itself."""

    size_bytes: int | None = Field(default=None, gt=0)


class UploadCompleteResponse(BaseModel):
    upload: UploadSessionRead
    message: str
