"""Resumable upload session and its parts."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import UploadStatus
from app.db.base import Base, created_at_column, updated_at_column, uuid_pk


class UploadSession(Base):
    __tablename__ = "upload_sessions"

    id: Mapped[uuid.UUID] = uuid_pk()
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(160), nullable=True)
    expected_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    received_size: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    chunk_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_parts: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default=UploadStatus.UPLOADING.value, index=True
    )
    temporary_path: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    parts: Mapped[list[UploadPart]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="UploadPart.part_number",
    )


class UploadPart(Base):
    __tablename__ = "upload_parts"
    __table_args__ = (
        UniqueConstraint("upload_session_id", "part_number", name="uq_upload_parts_session_part"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    upload_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("upload_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    part_number: Mapped[int] = mapped_column(Integer, nullable=False)
    byte_offset: Mapped[int] = mapped_column(BigInteger, nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    received_at: Mapped[datetime] = created_at_column()

    session: Mapped[UploadSession] = relationship(back_populates="parts")
