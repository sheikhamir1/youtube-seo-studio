"""Job, SEO context and system-related schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.core.constants import LANGUAGE_OPTIONS  # noqa: F401  (documented option list)
from app.schemas.common import ORMModel

MAX_PREFLIGHT_CHUNKS = 10_000


class SEOContextInput(BaseModel):
    """Optional user metadata; every field may stay empty."""

    video_title: str | None = Field(default=None, max_length=300)
    primary_keyword: str | None = Field(default=None, max_length=200)
    secondary_keywords: list[str] = Field(default_factory=list, max_length=30)
    target_audience: str | None = Field(default=None, max_length=300)
    content_language: str = Field(default="auto", max_length=80)
    seo_language: str = Field(default="auto", max_length=80)
    content_type: str = Field(default="auto", max_length=80)
    tone: str = Field(default="auto", max_length=80)

    @field_validator("secondary_keywords")
    @classmethod
    def _clean_keywords(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        cleaned: list[str] = []
        for item in value:
            text = (item or "").strip()
            if text and text.lower() not in seen:
                seen.add(text.lower())
                cleaned.append(text)
        return cleaned


class JobCreateRequest(BaseModel):
    upload_id: uuid.UUID
    selected_model: str = Field(min_length=1, max_length=120)
    prompt_template_id: uuid.UUID
    seo_context: SEOContextInput = Field(default_factory=SEOContextInput)
    # Idempotency guard so a double-clicked button cannot create two jobs.
    client_request_id: str | None = Field(default=None, max_length=120)


class JobRead(ORMModel):
    id: uuid.UUID
    upload_session_id: uuid.UUID | None
    original_filename: str
    source_size_bytes: int
    video_duration_seconds: float | None
    audio_stream_index: int | None
    audio_stream_language: str | None
    audio_stream_start_offset_seconds: float
    audio_duration_seconds: float | None
    status: str
    stage: str
    progress_percent: float
    current_chunk_index: int | None
    total_chunks: int | None
    selected_model: str
    prompt_template_id: uuid.UUID | None
    prompt_template_name_snapshot: str | None
    pipeline_config: dict[str, Any]
    seo_context: dict[str, Any]
    current_error_code: str | None
    current_error_message: str | None
    failed_stage: str | None
    failed_chunk_index: int | None
    attempt_count: int
    cancel_requested: bool
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    failed_at: datetime | None
    last_heartbeat_at: datetime | None


class JobSummary(ORMModel):
    id: uuid.UUID
    original_filename: str
    status: str
    stage: str
    progress_percent: float
    selected_model: str
    video_duration_seconds: float | None
    created_at: datetime
    completed_at: datetime | None
    current_seo_score: int | None = None
    prompt_template_name_snapshot: str | None = None
    total_chunks: int | None = None


class JobListResponse(BaseModel):
    items: list[JobSummary]
    total: int
    page: int
    page_size: int


class ChunkRead(ORMModel):
    id: uuid.UUID
    chunk_index: int
    start_seconds: float
    end_seconds: float
    duration_seconds: float
    status: str
    attempt_count: int
    estimated_input_tokens: int | None
    actual_input_tokens: int | None
    actual_output_tokens: int | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None


class JobEventRead(ORMModel):
    id: int
    job_id: uuid.UUID
    sequence_number: int
    event_type: str
    level: str
    stage: str | None
    message: str
    progress_percent: float | None
    chunk_index: int | None
    payload: dict[str, Any] | None
    created_at: datetime


class JobEventListResponse(BaseModel):
    items: list[JobEventRead]
    total: int
    page: int
    page_size: int


class PipelineConfigRead(BaseModel):
    chunk_duration_seconds: float
    chunk_overlap_seconds: float
    audio_format: str
    gemini_min_interval_seconds: float
    model: str
    language: str
    max_topics_per_chunk: int
    max_retries: int


class ProcessingDetailsRead(BaseModel):
    model: str
    prompt_template_name_snapshot: str | None
    chunk_count: int
    completed_chunks: int
    failed_chunks: int
    gemini_requests: int
    retry_count: int
    input_tokens: int | None
    output_tokens: int | None
    durations_seconds: dict[str, float | None]
    pipeline_config: dict[str, Any]


class JobDetailResponse(BaseModel):
    job: JobRead
    chunks: list[ChunkRead]
    current_result_id: uuid.UUID | None = None
    preflight: PreflightEstimate | None = None


class PreflightEstimate(BaseModel):
    """Honest, documented estimate - never a guarantee."""

    duration_seconds: float | None
    duration_formatted: str
    estimated_chunks: int
    estimated_map_requests: int
    estimated_reduce_requests: int
    estimated_total_requests: int
    estimated_input_tokens_per_chunk: int
    estimated_total_tokens: int
    requests_today: int
    rpd_limit: int
    exceeds_daily_budget: bool
    warning: str | None = None


JobDetailResponse.model_rebuild()
