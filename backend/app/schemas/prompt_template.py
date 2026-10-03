"""Prompt template CRUD schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel


class PromptTemplateBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    system_prompt: str = Field(min_length=1)
    user_prompt_template: str = Field(min_length=1)

    @field_validator("name")
    @classmethod
    def _trim_name(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("Template name is required.")
        return name

    @field_validator("system_prompt", "user_prompt_template")
    @classmethod
    def _require_body(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Prompt content is required.")
        return value


class PromptTemplateCreate(PromptTemplateBase):
    """Creation payload: every base field is required."""


class PromptTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    system_prompt: str | None = None
    user_prompt_template: str | None = None

    @field_validator("name")
    @classmethod
    def _trim(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class PromptTemplateRead(ORMModel):
    id: uuid.UUID
    name: str
    description: str | None
    system_prompt: str
    user_prompt_template: str
    is_default: bool
    created_at: datetime
    updated_at: datetime


class PromptTemplatePreviewRequest(BaseModel):
    user_prompt_template: str = Field(min_length=1)
    sample_context: dict[str, object] | None = None


class PromptTemplatePreviewResponse(BaseModel):
    rendered_system_prompt: str | None = None
    rendered_user_prompt: str
    used_variables: list[str]
    available_variables: list[str]
    warnings: list[str] = Field(default_factory=list)
