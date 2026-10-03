"""Lightweight test doubles (no database, no network, no real clock)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from app.services.ai.client import StructuredResponse, UploadedFile, UsageMetadata

# Shared sample data for prompt rendering and mock-AI tests.
SAMPLE_TIMELINE = [
    {
        "topic": "Introduction",
        "summary": "Frames the session.",
        "start_seconds": 0,
        "end_seconds": 600,
        "source_chunk_indices": [0],
    },
    {
        "topic": "Core concepts",
        "summary": "Detailed explanation.",
        "start_seconds": 600,
        "end_seconds": 3600,
        "source_chunk_indices": [0, 1],
    },
]

SAMPLE_SEO_CONTEXT = {
    "video_title": "Advanced RAG Course",
    "primary_keyword": "vector search",
    "secondary_keywords": ["embeddings", "semantic search"],
    "target_audience": "Developers",
    "content_language": "Urdu/English",
    "seo_language": "English",
    "content_type": "Course",
    "tone": "Educational",
}


class FakeClock:
    """Monotonic + wall clock that only advances when the test moves it."""

    def __init__(self, start: float = 1000.0) -> None:
        self._monotonic = start
        self._wall = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self._monotonic

    def now(self) -> datetime:
        return self._wall

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.advance(seconds)

    def advance(self, seconds: float) -> None:
        self._monotonic += seconds
        self._wall += timedelta(seconds=seconds)


class FakeHistory:
    """In-memory equivalent of AIRequestLog window queries."""

    def __init__(self) -> None:
        self.starts: list[datetime] = []
        self.tokens: list[tuple[datetime, int]] = []

    async def last_request_start(self) -> datetime | None:
        return max(self.starts) if self.starts else None

    async def requests_since(self, since: datetime) -> int:
        return sum(1 for start in self.starts if start >= since)

    async def tokens_since(self, since: datetime) -> int:
        return sum(tokens for when, tokens in self.tokens if when >= since)

    def record(self, when: datetime, tokens: int = 1000) -> None:
        self.starts.append(when)
        self.tokens.append((when, tokens))


class FakeGeminiClient:
    """Deterministic client with scripted failures for retry tests."""

    def __init__(
        self,
        *,
        payload: dict[str, Any] | None = None,
        failures: int = 0,
        exception: Exception | None = None,
    ) -> None:
        self.payload = payload or {"topics": []}
        self.failures = failures
        self.exception = exception or RuntimeError("503 Service Unavailable")
        self.calls = 0
        self.uploaded: list[str] = []
        self.deleted: list[str] = []

    @property
    def provider_name(self) -> str:
        return "fake"

    async def upload_file(self, path, *, mime_type=None) -> UploadedFile:
        self.uploaded.append(str(path))
        return UploadedFile(name=f"files/{uuid.uuid4().hex[:8]}", uri="mock://file", mime_type="audio/flac")

    async def wait_until_ready(self, file: UploadedFile) -> UploadedFile:
        return file

    async def generate_structured(
        self,
        *,
        model: str,
        system_instruction: str,
        user_prompt: str,
        schema: dict[str, Any],
        audio_file: UploadedFile | None = None,
        thinking_level: str | None = None,
    ) -> StructuredResponse:
        self.calls += 1
        if self.calls <= self.failures:
            raise self.exception
        return StructuredResponse(
            payload=self.payload,
            usage=UsageMetadata(input_tokens=100, output_tokens=50, total_tokens=150),
        )

    async def delete_file(self, file: UploadedFile) -> None:
        self.deleted.append(file.name)


class FakeAIRequestRepo:
    """Records attempts the same way AIRequestRepository does."""

    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    async def start(self, **kwargs: Any):
        record = type("LogRecord", (), {})()
        record.id = uuid.uuid4()
        record.attempt_number = kwargs.get("attempt_number")
        self.records.append({"status": "PENDING", **kwargs})
        return record

    async def finish_success(self, record_id, **kwargs: Any) -> None:
        self.records[-1].update({"status": "SUCCESS", **kwargs})

    async def finish_failure(self, record_id, **kwargs: Any) -> None:
        self.records[-1].update({"status": "FAILED", **kwargs})

    async def request_count_for_job(self, job_id) -> int:
        return len(self.records)

    async def retry_count_for_job(self, job_id) -> int:
        return sum(1 for record in self.records if (record.get("attempt_number") or 1) > 1)


class FakeEventRepo:
    """Collects events in memory (SSE behaviour is asserted from this list)."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def append(self, **kwargs: Any):
        event = type("Event", (), {})()
        event.id = len(self.events) + 1
        event.message = kwargs.get("message", "")
        self.events.append(kwargs)
        return event


class FakeChunkRepo:
    """Minimal chunk repository double for Map-phase tests."""

    def __init__(self, chunk: Any) -> None:
        self.chunk = chunk
        self.marked: dict[str, Any] = {}

    async def mark_processing(self, chunk_id) -> None:
        self.marked["processing"] = True

    async def mark_completed(self, chunk_id, **kwargs: Any) -> None:
        self.marked["completed"] = kwargs

    async def mark_failed(self, chunk_id, **kwargs: Any) -> None:
        self.marked["failed"] = kwargs

    async def mark_file_cleaned(self, chunk_id) -> None:
        self.marked["file_cleaned"] = True


class FakeChunk:
    """Stand-in for an AudioChunk row."""

    def __init__(self, *, chunk_index: int, start: float, end: float, path: str) -> None:
        self.id = uuid.uuid4()
        self.chunk_index = chunk_index
        self.start_seconds = start
        self.end_seconds = end
        self.duration_seconds = end - start
        self.local_path = path
        self.status = "PENDING"
        self.attempt_count = 0
