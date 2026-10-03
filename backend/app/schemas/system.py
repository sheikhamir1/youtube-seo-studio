"""System status / model registry / quota schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DependencyStatus(BaseModel):
    ok: bool
    detail: str | None = None


class DiskInfo(BaseModel):
    path: str
    total_bytes: float
    used_bytes: float
    free_bytes: float
    used_percent: float


class WorkerStatusRead(BaseModel):
    worker_id: str
    status: str
    last_heartbeat_at: str | None
    heartbeat_age_seconds: float | None
    current_job_id: str | None
    current_stage: str | None
    alive: bool


class SystemStatus(BaseModel):
    app_env: str
    app_name: str
    database: DependencyStatus
    ffmpeg: DependencyStatus
    ffprobe: DependencyStatus
    gemini_key_configured: bool
    ai_provider: str
    default_model: str
    worker: WorkerStatusRead | None
    data_dir: str
    disk: DiskInfo | None
    queued_jobs: int
    active_jobs: int


class ModelProfile(BaseModel):
    id: str
    label: str
    supports_audio: bool
    supports_structured_output: bool
    capability_known: bool = True
    thinking_level_default: str | None = None
    notes: str | None = None
    is_default: bool = False
    #: True when the model is enabled in GEMINI_ALLOWED_MODELS and selectable.
    is_configured: bool = True


class ModelsResponse(BaseModel):
    models: list[ModelProfile]
    default_model: str
    #: Model ids that may be selected (GEMINI_ALLOWED_MODELS).
    selectable_models: list[str] = []


class QuotaResponse(BaseModel):
    """Application-tracked usage only - never a claim about Google's own quota."""

    label: str = "Application-tracked usage"
    requests_today: int
    rpd_limit: int
    rolling_minute_requests: int
    rpm_limit: int
    rolling_minute_tokens: int
    tpm_limit: int
    min_interval_seconds: float
    estimated_next_request_tokens: int | None = None
    daily_budget_reached: bool = False
    warning: str | None = None


class CleanupResponse(BaseModel):
    aborted_upload_sessions: int
    deleted_files: int
    freed_bytes: int
    orphan_directories: list[str] = Field(default_factory=list)
    details: list[dict[str, Any]] = Field(default_factory=list)


class StorageUsageResponse(BaseModel):
    jobs: int
    source_bytes: float
    audio_bytes: float
    chunk_bytes: float
    output_bytes: float
    total_bytes: float
    available_bytes: float
    data_dir: str
