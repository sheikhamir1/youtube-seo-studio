"""SEO output schemas (Reduce phase result) and validation helpers."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.core.constants import DESCRIPTION_MAX_CHARS, TITLE_MAX_CHARS
from app.schemas.common import ORMModel


class SEOOutput(BaseModel):
    """Structured Reduce output - the only fields the model controls."""

    title: str
    description: str
    tags: list[str]
    seo_score: int
    improvement_suggestions: str
    thumbnail_prompt: str

    @field_validator("title", "description", "improvement_suggestions", "thumbnail_prompt")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        text = (value or "").strip()
        if not text:
            raise ValueError("must not be empty")
        return text

    @field_validator("tags")
    @classmethod
    def _clean_tags(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        cleaned: list[str] = []
        for tag in value:
            text = (tag or "").strip().lstrip("#").strip()
            if not text:
                continue
            key = text.casefold()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(text)
        if not cleaned:
            raise ValueError("at least one tag is required")
        return cleaned


class Chapter(BaseModel):
    seconds: float = Field(ge=0)
    timestamp: str
    title: str

    @field_validator("title")
    @classmethod
    def _title(cls, value: str) -> str:
        text = (value or "").strip()
        if not text:
            raise ValueError("chapter title must not be empty")
        return text


class ChapterValidationReport(BaseModel):
    valid: bool
    chapters: list[Chapter] = Field(default_factory=list)
    checks: dict[str, bool] = Field(default_factory=dict)
    issues: list[str] = Field(default_factory=list)
    repairs_applied: list[str] = Field(default_factory=list)


class SEOResultRead(ORMModel):
    id: uuid.UUID
    job_id: uuid.UUID
    version_number: int
    title: str
    description: str
    tags: list[str]
    seo_score: int
    improvement_suggestions: str
    thumbnail_prompt: str
    model: str
    prompt_template_id: uuid.UUID | None
    prompt_template_name_snapshot: str | None
    validation_metadata: dict[str, Any] | None
    chapters: list[dict[str, Any]] | None
    is_current: bool
    edited_by_user: bool
    created_at: datetime
    updated_at: datetime


class SEOResultUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    improvement_suggestions: str | None = None
    thumbnail_prompt: str | None = None
    seo_score: int | None = Field(default=None, ge=0, le=100)

    @field_validator("title")
    @classmethod
    def _title_limit(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        if not text:
            raise ValueError("Title must not be empty.")
        if len(text) > TITLE_MAX_CHARS:
            raise ValueError(f"Title must be at most {TITLE_MAX_CHARS} characters.")
        return text

    @field_validator("description")
    @classmethod
    def _description_limit(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if len(value.strip()) == 0:
            raise ValueError("Description must not be empty.")
        if len(value) > DESCRIPTION_MAX_CHARS:
            raise ValueError(f"Description must be at most {DESCRIPTION_MAX_CHARS} characters.")
        return value


class RegenerateRequest(BaseModel):
    prompt_template_id: uuid.UUID | None = None
    selected_model: str | None = Field(default=None, max_length=120)


SEOResultRead.model_rebuild()
