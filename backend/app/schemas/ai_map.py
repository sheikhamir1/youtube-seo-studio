"""Map-phase schemas: what Gemini must return for each audio chunk."""

from __future__ import annotations

import math

from pydantic import BaseModel, Field, field_validator

from app.core.constants import TIMESTAMP_EPSILON_SECONDS


class MapTopic(BaseModel):
    topic: str = Field(min_length=1, max_length=400)
    summary: str = Field(min_length=1, max_length=2000)
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)

    @field_validator("topic", "summary")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        text = (value or "").strip()
        if not text:
            raise ValueError("must not be empty")
        return text

    @field_validator("start_seconds", "end_seconds")
    @classmethod
    def _finite(cls, value: float) -> float:
        # Reject NaN / Infinity outright - they are never acceptable output.
        if value is None or math.isnan(value) or math.isinf(value):
            raise ValueError("timestamp must be a finite number")
        if value < 0:
            raise ValueError("timestamp must not be negative")
        return value

    @field_validator("end_seconds")
    @classmethod
    def _ordered(cls, value: float, info) -> float:
        start = info.data.get("start_seconds")
        if start is not None and value <= start:
            raise ValueError("end_seconds must be greater than start_seconds")
        return value


class MapResponse(BaseModel):
    topics: list[MapTopic] = Field(default_factory=list)


def validate_map_response(
    payload: dict,
    *,
    chunk_duration_seconds: float,
    max_topics: int,
    epsilon: float = TIMESTAMP_EPSILON_SECONDS,
) -> tuple[MapResponse, list[str]]:
    """Validate a Map response and clamp only *tiny* floating point overshoot.

    Returns the parsed response plus a list of applied clamps (for logging).
    Major invalid data is rejected rather than silently repaired.
    """
    response = MapResponse.model_validate(payload)
    clamps: list[str] = []
    cleaned: list[MapTopic] = []

    for topic in response.topics:
        start = topic.start_seconds
        end = topic.end_seconds

        # Tolerate sub-second overshoot caused by model rounding only.
        if start < 0 and start > -epsilon:
            clamps.append(f"clamped negative start {start} -> 0")
            start = 0.0
        if end > chunk_duration_seconds and end <= chunk_duration_seconds + epsilon:
            clamps.append(f"clamped end {end} -> {chunk_duration_seconds}")
            end = chunk_duration_seconds

        if start < 0:
            raise ValueError(f"start_seconds {start} is negative")
        if end > chunk_duration_seconds:
            raise ValueError(f"end_seconds {end} exceeds chunk duration {chunk_duration_seconds}")
        if end <= start:
            raise ValueError(f"topic '{topic.topic}' has end <= start")

        cleaned.append(
            MapTopic(topic=topic.topic, summary=topic.summary, start_seconds=start, end_seconds=end)
        )

    if len(cleaned) > max_topics:
        raise ValueError(
            f"response contains {len(cleaned)} topics which exceeds the configured maximum of {max_topics}"
        )

    return MapResponse(topics=cleaned), clamps
