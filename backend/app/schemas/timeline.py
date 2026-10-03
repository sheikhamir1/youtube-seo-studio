"""Timeline schemas (normalized Map output)."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class TimelineTopic(BaseModel):
    """One normalized content topic on the video timeline."""

    topic: str
    summary: str
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    source_chunk_indices: list[int] = Field(default_factory=list)

    @field_validator("topic", "summary")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        text = (value or "").strip()
        if not text:
            raise ValueError("must not be empty")
        return text

    @field_validator("end_seconds")
    @classmethod
    def _ordered(cls, value: float, info) -> float:
        start = info.data.get("start_seconds")
        if start is not None and value <= start:
            raise ValueError("end_seconds must be greater than start_seconds")
        return value


class TimelineResponse(BaseModel):
    job_id: str
    video_duration_seconds: float | None
    topic_count: int
    topics: list[TimelineTopic]
    generated_at: str | None = None
    note: str = "AI-generated content timestamps (not frame-accurate)."
