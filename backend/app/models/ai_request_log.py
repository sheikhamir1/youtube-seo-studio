"""AIRequestLog: every Gemini inference attempt, retries included."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import AIRequestPhase, AIRequestStatus
from app.db.base import Base, created_at_column, uuid_pk


class AIRequestLog(Base):
    """Rate limiting, quota accounting and diagnostics all read this table."""

    __tablename__ = "ai_request_logs"
    __table_args__ = (
        Index("ix_ai_request_logs_started_at", "started_at"),
        Index("ix_ai_request_logs_job_id", "job_id"),
        Index("ix_ai_request_logs_phase", "phase"),
        Index("ix_ai_request_logs_status_started_at", "status", "started_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=True)
    audio_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("audio_chunks.id", ondelete="SET NULL"), nullable=True
    )
    phase: Mapped[str] = mapped_column(String(24), nullable=False, default=AIRequestPhase.MAP.value)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    estimated_input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    thinking_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default=AIRequestStatus.PENDING.value)
    http_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = created_at_column()
