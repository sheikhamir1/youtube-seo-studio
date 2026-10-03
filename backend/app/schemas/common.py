"""Shared schema helpers."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ORMModel(BaseModel):
    """Base for schemas read directly from SQLAlchemy objects."""

    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class ErrorDetail(BaseModel):
    code: str
    details: Any | None = None


class Envelope(BaseModel, Generic[T]):
    data: T | None = None
    message: str = "OK"
    error: ErrorDetail | None = None


class MessageResponse(BaseModel):
    message: str
