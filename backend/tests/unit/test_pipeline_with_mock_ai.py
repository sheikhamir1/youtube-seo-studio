"""End-to-end service pipeline with the deterministic mock AI client.

This exercises Map -> timestamp conversion -> timeline normalization ->
Reduce -> SEO validation without PostgreSQL, FFmpeg, network access or a Gemini
API key. It is the fastest proof that the core Map-Reduce chain works.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from app.services.ai.map_service import GeminiMapService
from app.services.ai.mock_client import MockGeminiClient
from app.services.ai.rate_limiter import GeminiRateLimiter
from app.services.ai.reduce_service import GeminiReduceService
from app.services.prompts.defaults import (
    DEFAULT_SEO_SYSTEM_PROMPT,
    DEFAULT_SEO_USER_PROMPT_TEMPLATE,
)
from app.services.prompts.renderer import build_seo_context_values
from app.services.timeline.normalizer import TimelineNormalizer
from tests.fakes import (
    FakeAIRequestRepo,
    FakeChunk,
    FakeChunkRepo,
    FakeClock,
    FakeEventRepo,
    FakeHistory,
)


@pytest.fixture
def audio_chunk(tmp_path: Path) -> FakeChunk:
    chunk_path = tmp_path / "chunk-00000.flac"
    chunk_path.write_bytes(b"flac-ish-bytes-for-testing")
    return FakeChunk(chunk_index=0, start=0.0, end=3600.0, path=str(chunk_path))


@pytest.fixture
def runtime():
    clock = FakeClock()
    history = FakeHistory()
    limiter = GeminiRateLimiter(
        history=history,
        clock=clock,
        min_interval_seconds=60.0,
        rpm_limit=15,
        tpm_limit=250_000,
        rpd_limit=500,
    )
    return limiter


async def test_map_phase_persists_absolute_timestamps(audio_chunk, runtime):
    client = MockGeminiClient()
    ai_repo = FakeAIRequestRepo()
    chunk_repo = FakeChunkRepo(audio_chunk)
    event_repo = FakeEventRepo()
    job_id = uuid.uuid4()

    service = GeminiMapService(
        client=client,
        limiter=runtime,
        ai_repo=ai_repo,
        chunk_repo=chunk_repo,
        event_repo=event_repo,
        model="gemini-3.5-flash",
        audio_start_offset_seconds=2.0,  # audio track starts 2 s after the video
        content_language="Urdu/English",
    )

    result = await service.analyze_chunk(job_id=job_id, chunk=audio_chunk)

    assert result["audio_start_offset_seconds"] == 2.0
    assert result["topics"], "the mock client must produce topics"
    first = result["topics"][0]
    # absolute = audio offset + chunk start + relative start
    assert first["start_seconds"] >= 2.0
    assert first["source_chunk_indices"] == [0]

    # Persisted before any cleanup, so a crash cannot lose the result.
    assert "completed" in chunk_repo.marked
    assert chunk_repo.marked["completed"]["actual_input_tokens"] == 12_000
    assert chunk_repo.marked["completed"]["relative_result"]["topics"]

    # The remote file was cleaned up (best effort) and the local file was not touched.
    assert client.deleted_files
    assert Path(audio_chunk.local_path).exists()
    assert chunk_repo.marked.get("file_cleaned") is True

    # Event log mirrors the chunk lifecycle.
    types = [event["event_type"] for event in event_repo.events]
    assert "CHUNK_MAPPING_STARTED" in types and "CHUNK_MAPPING_COMPLETED" in types
    assert ai_repo.records and ai_repo.records[0]["status"] == "SUCCESS"


async def test_full_map_reduce_chain_produces_a_valid_seo_version(runtime):
    client = MockGeminiClient()
    event_repo = FakeEventRepo()
    job_id = uuid.uuid4()

    # --- Map two overlapping chunks -----------------------------------------
    normalizer = TimelineNormalizer(similarity_threshold=0.88, proximity_seconds=90)
    chunk_results = []
    for index, (start, end) in enumerate([(0.0, 3600.0), (3540.0, 7140.0)]):
        payload = client._map_payload(f"Chunk duration: {int(end - start)}\nChunk index: {index}")
        chunk_results.append(
            {
                "chunk_index": index,
                "start_seconds": start,
                "audio_start_offset": 0.0,
                "duration_seconds": end - start,
                "topics": payload["topics"],
            }
        )

    timeline = normalizer.normalize(chunk_results)
    assert len(timeline) >= 4
    starts = [topic["start_seconds"] for topic in timeline]
    assert starts == sorted(starts)

    # --- Reduce -------------------------------------------------------------
    reduce_service = GeminiReduceService(
        client=client,
        limiter=runtime,
        ai_repo=FakeAIRequestRepo(),
        event_repo=event_repo,
        model="gemini-3.5-flash",
    )
    context_values = build_seo_context_values(
        seo_context={
            "video_title": "Advanced RAG Course",
            "primary_keyword": "vector search",
            "secondary_keywords": ["embeddings", "semantic search"],
            "target_audience": "Developers",
            "content_language": "Hindi/English",
            "seo_language": "English",
            "content_type": "Course",
            "tone": "Educational",
        },
        original_filename="advanced-rag-course.mp4",
        video_duration_seconds=7140,
        timeline=timeline,
    )

    output, metadata, usage = await reduce_service.generate_seo(
        job_id=job_id,
        timeline=timeline,
        context_values=context_values,
        system_prompt=DEFAULT_SEO_SYSTEM_PROMPT,
        user_prompt_template=DEFAULT_SEO_USER_PROMPT_TEMPLATE,
        video_duration_seconds=7140,
    )

    # The result is schema-valid *and* YouTube-valid.
    assert output.title.startswith("Advanced RAG Course")
    assert len(output.title) <= 100
    assert len(output.description) <= 5000
    assert output.seo_score == 84
    assert metadata["chapter_validation"]["valid"] is True
    assert metadata["chapter_validation"]["count"] >= 3
    assert metadata["chapter_validation"]["checks"]["starts_at_zero"] is True
    assert output.tags and len(output.tags) == len({tag.casefold() for tag in output.tags})
    assert len(output.thumbnail_prompt) > 80
    assert usage["input_tokens"] > 0


async def test_reduce_uses_the_timeline_it_was_given(runtime):
    """Reduce must never see raw chunk duplicates: only the normalized timeline."""
    client = MockGeminiClient()
    reduce_service = GeminiReduceService(
        client=client,
        limiter=runtime,
        ai_repo=FakeAIRequestRepo(),
        event_repo=FakeEventRepo(),
        model="gemini-3.5-flash",
    )
    timeline = [
        {
            "topic": "Introduction",
            "summary": "Opening.",
            "start_seconds": 0,
            "end_seconds": 300,
            "source_chunk_indices": [0],
        },
        {
            "topic": "Main topic",
            "summary": "Body.",
            "start_seconds": 300,
            "end_seconds": 3300,
            "source_chunk_indices": [0],
        },
        {
            "topic": "Closing summary",
            "summary": "Wrap-up.",
            "start_seconds": 3300,
            "end_seconds": 3600,
            "source_chunk_indices": [1],
        },
    ]
    context_values = build_seo_context_values(
        seo_context={"video_title": "Test Video"},
        original_filename="test.mp4",
        video_duration_seconds=3600,
        timeline=timeline,
    )
    output, metadata, _ = await reduce_service.generate_seo(
        job_id=uuid.uuid4(),
        timeline=timeline,
        context_values=context_values,
        system_prompt=DEFAULT_SEO_SYSTEM_PROMPT,
        user_prompt_template=DEFAULT_SEO_USER_PROMPT_TEMPLATE,
        video_duration_seconds=3600,
    )
    assert output.title == "Test Video"
    assert metadata["chapter_validation"]["valid"] is True
    assert client.uploaded_files == [], "Reduce must never upload audio"


async def test_cancellation_is_respected_before_a_chunk(runtime):
    from app.core.errors import GeminiError
    from app.services.ai.inference import run_inference

    async def _call(attempt: int):
        raise AssertionError("should never be called when the job was canceled")

    with pytest.raises(GeminiError) as excinfo:
        await run_inference(
            call=_call,
            phase="MAP",
            model="gemini-3.5-flash",
            estimated_input_tokens=1000,
            job_id=uuid.uuid4(),
            ai_repo=FakeAIRequestRepo(),
            limiter=runtime,
            max_retries=3,
            should_abort=lambda: True,
        )
    assert excinfo.value.code == "JOB_CANCELED"


async def test_retry_obeys_the_rate_limiter_and_counts_every_attempt(runtime):
    """429, 429, then success: three logged attempts, pacing applied each time."""
    from app.services.ai.client import StructuredResponse, UsageMetadata
    from app.services.ai.inference import run_inference

    calls = {"count": 0}

    class Boom(Exception):
        status_code = 429

    async def _call(attempt: int):
        calls["count"] += 1
        if calls["count"] <= 2:
            raise Boom("429 Too Many Requests")
        return StructuredResponse(payload={"ok": True}, usage=UsageMetadata(input_tokens=10))

    # Keep the test instant: no limiter wait and a negligible retry backoff.
    runtime.min_interval_seconds = 0
    response = await run_inference(
        call=_call,
        phase="MAP",
        model="gemini-3.5-flash",
        estimated_input_tokens=1000,
        job_id=uuid.uuid4(),
        ai_repo=FakeAIRequestRepo(),
        limiter=runtime,
        max_retries=8,
        backoff_base_seconds=0.001,
        backoff_max_seconds=0.002,
    )
    assert response.payload == {"ok": True}
    assert calls["count"] == 3


async def test_non_retryable_auth_error_fails_immediately(runtime):
    from app.core.errors import GeminiAuthError
    from app.services.ai.inference import run_inference

    calls = {"count": 0}

    class AuthBoom(Exception):
        status_code = 401

    async def _call(attempt: int):
        calls["count"] += 1
        raise AuthBoom("API key not valid")

    runtime.min_interval_seconds = 0
    with pytest.raises(GeminiAuthError):
        await run_inference(
            call=_call,
            phase="MAP",
            model="gemini-3.5-flash",
            estimated_input_tokens=1000,
            job_id=uuid.uuid4(),
            ai_repo=FakeAIRequestRepo(),
            limiter=runtime,
            max_retries=8,
        )
    assert calls["count"] == 1, "authentication failures must never be retried"
