"""SQLAlchemy declarative base and shared column helpers."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, MetaData, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.timeutils import utcnow

# Explicit naming convention keeps Alembic migrations stable and readable.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base with a deterministic naming convention."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def uuid_pk() -> Mapped[uuid.UUID]:
    """UUID primary key column (generated application-side for portability)."""
    return mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)


def created_at_column() -> Mapped[datetime]:
    """UTC creation timestamp.

    The value is generated in Python *and* backed by a database default. The
    Python-side default matters for the async ORM: a server-side-only default
    leaves the attribute expired after INSERT, and touching it later would try
    to lazy-load outside the greenlet context (``MissingGreenlet``).
    """
    return mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
    )


def updated_at_column() -> Mapped[datetime]:
    """UTC last-modified timestamp, refreshed on every UPDATE from Python."""
    return mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
    )
