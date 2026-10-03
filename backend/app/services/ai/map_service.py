"""GeminiMapService: analyse one audio chunk at a time (exactly one request)."""

from __future__ import annotations

import json
from typing import Any

from app.core.config import settings
from app.core.enums import AIRequestPhase, EventLevel, JobEventType
from app.core.errors import ErrorCode, GeminiError
from app.core.logging import get_logger
from app.repositories.ai_requests import AIRequestRepository
from app.repositories.chunks import ChunkRepository
from app.repositories.events import JobEventRepository
from app.schemas.ai_map import validate_map_response
from app.services.ai.client import GeminiClient, UploadedFile
from app.services.ai.inference import AttemptOutcome, run_inference
from app.services.ai.rate_limiter import GeminiRateLimiter
from app.services.ai.usage import estimate_chunk_input_tokens
from app.services.prompts.defaults import MAP_SYSTEM_PROMPT, MAP_USER_PROMPT_TEMPLATE

logger = get_logger(__name__)

# JSON schema handed to Gemini for structured output.
MAP_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "topics": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "summary": {"type": "string"},
                    "start_seconds": {"type": "number"},
                    "end_seconds": {"type": "number"},
                },
                "required": ["topic", "summary", "start_seconds", "end_seconds"],
            },
        }
    },
    "required": ["topics"],
}


class GeminiMapService:
    """Uploads a chunk, runs inference, validates and persists the result."""

    def __init__(
        self,
        *,
        client: GeminiClient,
        limiter: GeminiRateLimiter,
        ai_repo: AIRequestRepository,
        chunk_repo: ChunkRepository,
        event_repo: JobEventRepository,
        model: str,
        audio_start_offset_seconds: float = 0.0,
        content_language: str = "auto",
        max_topics: int | None = None,
    ) -> None:
        self.client = client
        self.limiter = limiter
        self.ai_repo = ai_repo
        self.chunk_repo = chunk_repo
        self.event_repo = event_repo
        self.model = model
        self.audio_start_offset_seconds = audio_start_offset_seconds
        self.content_language = content_language
        self.max_topics = max_topics or settings.map_max_topics_per_chunk

    def build_user_prompt(self, *, chunk_index: int, chunk_start: float, duration: float) -> str:
        return MAP_USER_PROMPT_TEMPLATE.format(
            chunk_index=chunk_index,
            chunk_start_seconds=round(chunk_start, 2),
            chunk_duration_seconds=round(duration, 2),
            max_topics=self.max_topics,
            content_language=self.content_language or "auto (Hindi/Urdu/English mixed audio possible)",
        )

    async def analyze_chunk(self, *, job_id: Any, chunk: Any) -> dict[str, Any]:
        """Run the Map phase for a single chunk. Returns the normalized result."""
        from pathlib import Path

        chunk_path = Path(chunk.local_path)
        if not chunk_path.exists():
            await self.chunk_repo.mark_failed(
                chunk.id,
                code=ErrorCode.MEDIA_NOT_FOUND,
                message=f"Chunk file is missing on disk: {chunk_path.name}",
            )
            raise GeminiError(
                f"The local audio chunk {chunk.chunk_index} is missing on disk.",
                code=ErrorCode.MEDIA_NOT_FOUND,
                http_status=410,
            )

        user_prompt = self.build_user_prompt(
            chunk_index=chunk.chunk_index,
            chunk_start=chunk.start_seconds,
            duration=chunk.duration_seconds,
        )
        estimated_tokens = estimate_chunk_input_tokens(
            chunk.duration_seconds, system_prompt=MAP_SYSTEM_PROMPT, user_prompt=user_prompt
        )

        await self.chunk_repo.mark_processing(chunk.id)
        await self.event_repo.append(
            job_id=job_id,
            event_type=JobEventType.CHUNK_MAPPING_STARTED.value,
            message=f"Analyzing chunk {chunk.chunk_index} ({round(chunk.duration_seconds)}s audio)",
            stage="MAPPING",
            chunk_index=chunk.chunk_index,
            payload={"estimated_input_tokens": estimated_tokens},
        )

        uploaded: UploadedFile | None = None
        uploaded_once = False

        async def _call(attempt: int):
            nonlocal uploaded, uploaded_once
            if uploaded is None:
                uploaded = await self.client.upload_file(chunk_path, mime_type=_mime_for(chunk_path))
                uploaded = await self.client.wait_until_ready(uploaded)
                uploaded_once = True
            response = await self.client.generate_structured(
                model=self.model,
                system_instruction=MAP_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                schema=MAP_RESPONSE_SCHEMA,
                audio_file=uploaded,
                thinking_level=settings.map_thinking_level,
            )
            # Validate immediately: a schema failure is retried by the caller path
            # (structured output + repair allowance), never silently accepted.
            try:
                parsed, clamps = validate_map_response(
                    response.payload,
                    chunk_duration_seconds=chunk.duration_seconds,
                    max_topics=self.max_topics,
                )
            except Exception as exc:
                raise GeminiError(
                    "The Map response failed schema validation.",
                    details=str(exc)[:500],
                    code=ErrorCode.GEMINI_SCHEMA_ERROR,
                    http_status=502,
                ) from exc
            response.payload = parsed.model_dump()
            response.payload["_clamps"] = clamps
            return response

        async def _on_retry(outcome: AttemptOutcome) -> None:
            await self.event_repo.append(
                job_id=job_id,
                event_type=JobEventType.GEMINI_RETRY.value,
                level=EventLevel.WARNING.value,
                stage="MAPPING",
                chunk_index=chunk.chunk_index,
                message=(
                    f"Gemini retry {outcome.attempt} for chunk {chunk.chunk_index}: {outcome.error_code}"
                ),
                payload={
                    "attempt": outcome.attempt,
                    "error_code": outcome.error_code,
                    "http_status": outcome.http_status,
                    "retry_after": outcome.retry_after,
                },
            )

        response = await run_inference(
            call=_call,
            phase=AIRequestPhase.MAP.value,
            model=self.model,
            estimated_input_tokens=estimated_tokens,
            job_id=job_id,
            audio_chunk_id=chunk.id,
            ai_repo=self.ai_repo,
            limiter=self.limiter,
            max_retries=settings.max_gemini_retries,
            on_retry=_on_retry,
        )

        clamps = response.payload.pop("_clamps", [])
        topics = response.payload.get("topics", [])

        # Convert chunk-relative timestamps to absolute video timestamps now, so
        # restart safety never depends on re-reading provider output.
        normalized_topics = []
        for topic in topics:
            absolute_start = (
                self.audio_start_offset_seconds + float(chunk.start_seconds) + float(topic["start_seconds"])
            )
            absolute_end = (
                self.audio_start_offset_seconds + float(chunk.start_seconds) + float(topic["end_seconds"])
            )
            normalized_topics.append(
                {
                    "topic": topic["topic"],
                    "summary": topic["summary"],
                    "start_seconds": round(absolute_start, 3),
                    "end_seconds": round(absolute_end, 3),
                    "source_chunk_indices": [int(chunk.chunk_index)],
                }
            )

        normalized_result = {
            "chunk_index": int(chunk.chunk_index),
            "chunk_start_seconds": float(chunk.start_seconds),
            "audio_start_offset_seconds": self.audio_start_offset_seconds,
            "topics": normalized_topics,
            "clamped_values": clamps,
        }

        # Persist BEFORE any local cleanup: this is what makes resume safe.
        await self.chunk_repo.mark_completed(
            chunk.id,
            relative_result={"topics": topics, "clamps": clamps},
            normalized_result=normalized_result,
            actual_input_tokens=response.usage.input_tokens,
            actual_output_tokens=response.usage.output_tokens,
            gemini_file_name=uploaded.name if uploaded else None,
            gemini_file_uri=uploaded.uri if uploaded else None,
        )

        await self.event_repo.append(
            job_id=job_id,
            event_type=JobEventType.CHUNK_MAPPING_COMPLETED.value,
            level=EventLevel.SUCCESS.value,
            stage="MAPPING",
            chunk_index=chunk.chunk_index,
            message=f"Chunk {chunk.chunk_index} completed with {len(normalized_topics)} topics",
            payload={
                "topics": len(normalized_topics),
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "clamps": clamps,
            },
        )

        # Remote cleanup is best effort: a failure here never fails the job.
        if uploaded is not None and uploaded_once:
            try:
                await self.client.delete_file(uploaded)
            except Exception as exc:
                logger.warning(
                    "gemini_file_cleanup_failed chunk=%s error=%s", chunk.chunk_index, str(exc)[:200]
                )
                await self.event_repo.append(
                    job_id=job_id,
                    event_type=JobEventType.GEMINI_FILE_CLEANUP_FAILED.value,
                    level=EventLevel.WARNING.value,
                    stage="MAPPING",
                    chunk_index=chunk.chunk_index,
                    message="Remote Gemini file cleanup failed (job continues).",
                    payload={"error": str(exc)[:300]},
                )
            else:
                await self.chunk_repo.mark_file_cleaned(chunk.id)

        logger.info("map_chunk_done chunk=%s topics=%s", chunk.chunk_index, len(normalized_topics))
        return normalized_result


def _mime_for(path) -> str:
    suffix = path.suffix.lower()
    return {
        ".flac": "audio/flac",
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
    }.get(suffix, "audio/flac")


def map_response_schema_json() -> str:
    return json.dumps(MAP_RESPONSE_SCHEMA)


__all__ = ["MAP_RESPONSE_SCHEMA", "GeminiMapService", "map_response_schema_json"]
