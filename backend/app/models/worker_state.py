"""WorkerState: heartbeat row proving the worker subsystem is alive."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import WorkerStatus
from app.db.base import Base, uuid_pk


class WorkerState(Base):
    __tablename__ = "worker_states"

    id: Mapped[uuid.UUID] = uuid_pk()
    worker_id: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=WorkerStatus.STARTING.value)
    last_heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    current_job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True
    )
    current_stage: Mapped[str | None] = mapped_column(String(24), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
