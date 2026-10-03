"""SEOResult: an immutable-ish SEO version produced by the Reduce phase."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, created_at_column, updated_at_column, uuid_pk


class SEOResult(Base):
    __tablename__ = "seo_results"
    __table_args__ = (
        UniqueConstraint("job_id", "version_number", name="uq_seo_results_job_id_version_number"),
        CheckConstraint("seo_score >= 0 AND seo_score <= 100", name="seo_score_range"),
        Index("ix_seo_results_job_id_is_current", "job_id", "is_current"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    seo_score: Mapped[int] = mapped_column(Integer, nullable=False)
    improvement_suggestions: Mapped[str] = mapped_column(Text, nullable=False)
    thumbnail_prompt: Mapped[str] = mapped_column(Text, nullable=False)

    model: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_template_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("prompt_templates.id", ondelete="SET NULL"), nullable=True
    )
    prompt_template_name_snapshot: Mapped[str | None] = mapped_column(String(200), nullable=True)

    raw_response: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    validation_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    chapters: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)

    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    edited_by_user: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()

    job: Mapped[Job] = relationship(back_populates="results")  # noqa: F821
