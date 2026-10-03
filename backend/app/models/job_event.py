"""JobEvent: append-only processing log used for SSE and the log page."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import EventLevel
from app.db.base import (
    Base,
    created_at_column,
    uuid_pk,  # noqa: F401  (kept for symmetry)
)


class JobEvent(Base):
    __tablename__ = "job_events"
    __table_args__ = (Index("ix_job_events_job_id_sequence_number", "job_id", "sequence_number"),)

    # BIGSERIAL primary key: SSE "Last-Event-ID" maps directly onto this id.
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence_number: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)
    level: Mapped[str] = mapped_column(String(12), nullable=False, default=EventLevel.INFO.value)
    stage: Mapped[str | None] = mapped_column(String(24), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    progress_percent: Mapped[float | None] = mapped_column(nullable=True)
    chunk_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = created_at_column()

    job: Mapped[Job] = relationship(back_populates="events")  # noqa: F821
