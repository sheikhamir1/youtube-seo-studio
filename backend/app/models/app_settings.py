"""AppSettings: one local record for non-secret mutable settings.

Secrets (GEMINI_API_KEY) never live in the database - they come from the
environment only.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Float, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, updated_at_column


class AppSettings(Base):
    __tablename__ = "app_settings"

    # Single-row table: a fixed integer primary key keeps it simple and safe.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)

    default_model: Mapped[str] = mapped_column(String(120), nullable=False)
    allowed_models: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)

    gemini_rpm_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    gemini_tpm_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=250_000)
    gemini_rpd_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=500)
    gemini_min_interval_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=60.0)

    chunk_duration_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=3600.0)
    chunk_overlap_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=60.0)
    map_max_topics_per_chunk: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    max_gemini_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    max_schema_repair_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    audio_format: Mapped[str] = mapped_column(String(12), nullable=False, default="flac")

    updated_at: Mapped[datetime] = updated_at_column()
