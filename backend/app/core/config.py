"""Central application configuration.

Every tunable value used by business logic lives here (or in the database
AppSettings record) and is injected - never hardcoded across services.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven settings (see .env.example at the repository root)."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application -----------------------------------------------------------
    app_env: str = "development"
    app_name: str = "YouTube SEO Studio"
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"
    debug: bool = False
    enable_docs: bool = True

    # Database --------------------------------------------------------------
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/youtube_seo_studio"
    db_pool_size: int = 5
    db_max_overflow: int = 5
    db_pool_recycle_seconds: int = 1800
    db_echo: bool = False
    db_migrate_on_startup: bool = False

    # AI provider -----------------------------------------------------------
    ai_provider: str = "gemini"  # "gemini" | "mock"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_allowed_models: str = "gemini-3.5-flash-lite,gemini-3.8-flash"
    gemini_rpm_limit: int = 15
    gemini_tpm_limit: int = 250_000
    gemini_rpd_limit: int = 500
    gemini_min_interval_seconds: float = 60.0
    gemini_max_concurrency: int = 1
    gemini_file_poll_seconds: float = 3.0
    gemini_file_ready_timeout_seconds: float = 300.0
    audio_tokens_per_second: float = 32.0
    max_gemini_retries: int = 8
    max_schema_repair_attempts: int = 2
    map_thinking_level: str = "high"
    reduce_thinking_level: str = "high"

    # Processing ------------------------------------------------------------
    chunk_duration_seconds: float = 3600.0
    chunk_overlap_seconds: float = 60.0
    map_max_topics_per_chunk: int = 20
    audio_format: str = "flac"
    max_safe_input_tokens: int = 180_000
    reduce_safe_input_tokens: int = 180_000
    timeline_similarity_threshold: float = 0.88
    timeline_proximity_seconds: float = 90.0
    worker_poll_interval_seconds: float = 1.5
    # Backoff applied when the database (or any dependency) is temporarily
    # unavailable: the worker loop must survive transient outages.
    worker_error_backoff_seconds: float = 1.0
    worker_error_backoff_max_seconds: float = 30.0
    worker_stale_seconds: int = 120
    worker_id: str = "worker-1"
    upload_part_size_mb: int = 32
    stale_upload_hours: int = 24
    ffmpeg_binary: str = "ffmpeg"
    ffprobe_binary: str = "ffprobe"
    ffmpeg_extract_timeout_seconds: int = 60 * 60 * 12
    ffmpeg_chunk_timeout_seconds: int = 60 * 60 * 2

    # Storage ---------------------------------------------------------------
    data_dir: Path = Path("./data")

    # Web -------------------------------------------------------------------
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # ------------------------------------------------------------------ utils
    @field_validator("audio_format")
    @classmethod
    def _validate_audio_format(cls, value: str) -> str:
        allowed = {"flac", "wav"}
        normalized = value.strip().lower()
        if normalized not in allowed:
            raise ValueError(f"AUDIO_FORMAT must be one of {sorted(allowed)}")
        return normalized

    @field_validator("ai_provider")
    @classmethod
    def _validate_provider(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"gemini", "mock"}:
            raise ValueError("AI_PROVIDER must be 'gemini' or 'mock'")
        return normalized

    @field_validator("chunk_overlap_seconds")
    @classmethod
    def _validate_overlap(cls, value: float) -> float:
        if value < 0:
            raise ValueError("CHUNK_OVERLAP_SECONDS must be >= 0")
        return value

    # ---------------------------------------------------------------- derived
    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def allowed_models(self) -> list[str]:
        return [m.strip() for m in self.gemini_allowed_models.split(",") if m.strip()]

    @property
    def jobs_dir(self) -> Path:
        return self.data_dir / "jobs"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def is_test_provider(self) -> bool:
        return self.ai_provider == "mock"

    def ensure_data_dirs(self) -> None:
        """Create the storage roots if they do not exist yet."""
        for directory in (self.data_dir, self.jobs_dir, self.uploads_dir):
            directory.mkdir(parents=True, exist_ok=True)

    def job_dir(self, job_id: Any) -> Path:
        """Directory for a job's files, keyed by UUID - never by filename."""
        return self.jobs_dir / str(job_id)


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor (import-time friendly, overridable in tests)."""
    return Settings()


settings = get_settings()
