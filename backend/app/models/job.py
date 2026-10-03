"""Job: one analysis run over one uploaded video."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import JobStage, JobStatus
from app.db.base import Base, created_at_column, updated_at_column, uuid_pk


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_status_created_at", "status", "created_at"),
        Index("ix_jobs_updated_at", "updated_at"),
        Index("ix_jobs_last_heartbeat_at", "last_heartbeat_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    upload_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("upload_sessions.id", ondelete="SET NULL"), nullable=True
    )
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    source_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    video_duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    audio_stream_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    audio_stream_language: Mapped[str | None] = mapped_column(String(80), nullable=True)
    audio_stream_start_offset_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    audio_duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    media_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default=JobStatus.QUEUED.value, index=True
    )
    stage: Mapped[str] = mapped_column(String(24), nullable=False, default=JobStage.PENDING.value)
    progress_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    current_chunk_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_chunks: Mapped[int | None] = mapped_column(Integer, nullable=True)

    selected_model: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_template_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("prompt_templates.id", ondelete="SET NULL"), nullable=True
    )
    prompt_template_name_snapshot: Mapped[str | None] = mapped_column(String(200), nullable=True)
    system_prompt_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_prompt_template_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)

    pipeline_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    seo_context: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    timeline_snapshot: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)

    current_error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    current_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    failed_stage: Mapped[str | None] = mapped_column(String(24), nullable=True)
    failed_chunk_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    worker_id: Mapped[str | None] = mapped_column(String(80), nullable=True)

    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    chunks: Mapped[list[AudioChunk]] = relationship(  # noqa: F821 - forward ref
        back_populates="job",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    events: Mapped[list[JobEvent]] = relationship(  # noqa: F821
        back_populates="job",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="JobEvent.sequence_number",
    )
    results: Mapped[list[SEOResult]] = relationship(  # noqa: F821
        back_populates="job",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="SEOResult.version_number",
    )
