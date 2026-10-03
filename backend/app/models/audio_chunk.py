"""AudioChunk: one overlapping audio segment and its Map result."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import ChunkStatus
from app.db.base import Base, created_at_column, uuid_pk


class AudioChunk(Base):
    __tablename__ = "audio_chunks"
    __table_args__ = (
        UniqueConstraint("job_id", "chunk_index", name="uq_audio_chunks_job_id_chunk_index"),
        Index("ix_audio_chunks_job_id_status", "job_id", "status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    start_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    end_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    local_path: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default=ChunkStatus.PENDING.value, index=True
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    relative_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    normalized_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    estimated_input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    gemini_file_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    gemini_file_uri: Mapped[str | None] = mapped_column(Text, nullable=True)
    gemini_file_cleaned: Mapped[bool] = mapped_column(default=False, nullable=False)

    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = created_at_column()
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    job: Mapped[Job] = relationship(back_populates="chunks")  # noqa: F821
