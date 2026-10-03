"""GeminiReduceService: normalized timeline + template -> validated SEO output.

The Reduce phase never re-reads audio and never re-runs Map. When the timeline
is too large for one request, a hierarchical (Map-Reduce) summarisation pass
compresses it first - this is compression, not RAG.
"""

from __future__ import annotations

import json
from typing import Any

from app.core.config import settings
from app.core.constants import DESCRIPTION_MAX_CHARS, TITLE_MAX_CHARS
from app.core.enums import AIRequestPhase, EventLevel, JobEventType
from app.core.errors import ErrorCode, SEOValidationError
from app.core.logging import get_logger
from app.repositories.ai_requests import AIRequestRepository
from app.repositories.events import JobEventRepository
from app.schemas.seo import SEOOutput
from app.services.ai.client import GeminiClient
from app.services.ai.inference import AttemptOutcome, run_inference
from app.services.ai.rate_limiter import GeminiRateLimiter
from app.services.ai.usage import estimate_reduce_input_tokens
from app.services.prompts.renderer import build_reduce_prompts
from app.services.seo.validator import SEOValidator

logger = get_logger(__name__)

SEO_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "description": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "seo_score": {"type": "integer"},
        "improvement_suggestions": {"type": "string"},
        "thumbnail_prompt": {"type": "string"},
    },
    "required": [
        "title",
        "description",
        "tags",
        "seo_score",
        "improvement_suggestions",
        "thumbnail_prompt",
    ],
}

SUMMARY_SCHEMA: dict[str, Any] = {
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

REPAIR_INSTRUCTIONS = (
    "The previous response did not satisfy the application's validation rules:\n{issues}\n\n"
    "Return the complete corrected JSON object again. Keep the same structure, fix only the "
    "problems listed above, keep every chapter timestamp inside the supplied timeline, keep the "
    "title within {title_limit} characters and the description within {description_limit} characters."
)


class GeminiReduceService:
    def __init__(
        self,
        *,
        client: GeminiClient,
        limiter: GeminiRateLimiter,
        ai_repo: AIRequestRepository,
        event_repo: JobEventRepository,
        model: str,
    ) -> None:
        self.client = client
        self.limiter = limiter
        self.ai_repo = ai_repo
        self.event_repo = event_repo
        self.model = model

    # ------------------------------------------------------------------ public
    async def generate_seo(
        self,
        *,
        job_id: Any,
        timeline: list[dict[str, Any]],
        context_values: dict[str, Any],
        system_prompt: str,
        user_prompt_template: str,
        video_duration_seconds: float | None,
        max_repair_attempts: int | None = None,
    ) -> tuple[SEOOutput, dict[str, Any], dict[str, int | None]]:
        """Return (validated output, validation metadata, usage tokens)."""
        await self.event_repo.append(
            job_id=job_id,
            event_type=JobEventType.REDUCE_STARTED.value,
            message="Generating SEO assets from the normalized timeline",
            stage="REDUCTION",
            payload={"timeline_topics": len(timeline)},
        )

        working_timeline = await self._prepare_timeline(job_id=job_id, timeline=timeline)

        context = dict(context_values)
        # The Reduce prompt always receives the *compressed or full* timeline it
        # was prepared with - never the raw per-chunk duplicates.
        context["timeline_json"] = json.dumps(working_timeline, ensure_ascii=False, indent=2)
        context["timeline_text"] = "\n".join(
            f"- [{int(item.get('start_seconds', 0))}s - {int(item.get('end_seconds', 0))}s] "
            f"{item.get('topic', '')}: {item.get('summary', '')}"
            for item in working_timeline
        )

        rendered_system, rendered_user = build_reduce_prompts(
            template_system_prompt=system_prompt,
            template_user_prompt=user_prompt_template,
            context=context,
        )

        estimated_tokens = estimate_reduce_input_tokens(working_timeline)
        allowed_timestamps = [float(item.get("start_seconds", 0)) for item in working_timeline]
        allowed_windows = [
            (float(item.get("start_seconds", 0)), float(item.get("end_seconds", 0)))
            for item in working_timeline
        ]

        repair_budget = (
            settings.max_schema_repair_attempts if max_repair_attempts is None else max_repair_attempts
        )
        validator = SEOValidator(
            video_duration_seconds=video_duration_seconds,
            allowed_chapter_timestamps=allowed_timestamps,
            allowed_chapter_windows=allowed_windows,
        )

        prompt_suffix = ""
        last_error: SEOValidationError | None = None
        usage_totals = {"input_tokens": 0, "output_tokens": 0}

        for repair_attempt in range(repair_budget + 1):
            user_prompt = rendered_user + (f"\n\n{prompt_suffix}" if prompt_suffix else "")

            async def _call(attempt: int, _prompt: str = user_prompt):
                return await self.client.generate_structured(
                    model=self.model,
                    system_instruction=rendered_system,
                    user_prompt=_prompt,
                    schema=SEO_RESPONSE_SCHEMA,
                    audio_file=None,  # the video/audio is never re-sent to Reduce
                    thinking_level=settings.reduce_thinking_level,
                )

            def _on_retry(outcome: AttemptOutcome) -> None:
                logger.info("reduce_retry attempt=%s code=%s", outcome.attempt, outcome.error_code)

            response = await run_inference(
                call=_call,
                phase=AIRequestPhase.REDUCE.value if repair_attempt == 0 else AIRequestPhase.REPAIR.value,
                model=self.model,
                estimated_input_tokens=estimated_tokens,
                job_id=job_id,
                ai_repo=self.ai_repo,
                limiter=self.limiter,
                max_retries=settings.max_gemini_retries,
                on_retry=_on_retry,
            )

            raw_payload = response.payload
            for key in ("input_tokens", "output_tokens"):
                usage_totals[key] += int(
                    getattr(response.usage, "input_tokens" if key == "input_tokens" else "output_tokens") or 0
                )

            try:
                output, metadata = validator.validate(raw_payload)
            except SEOValidationError as exc:
                last_error = exc
                issues = _extract_issues(exc)
                if repair_attempt >= repair_budget:
                    await self.event_repo.append(
                        job_id=job_id,
                        event_type=JobEventType.SEO_VALIDATED.value,
                        level=EventLevel.ERROR.value,
                        stage="REDUCTION",
                        message="SEO validation failed after repair attempts.",
                        payload={"issues": issues},
                    )
                    raise
                prompt_suffix = REPAIR_INSTRUCTIONS.format(
                    issues="\n".join(f"- {issue}" for issue in issues) or "- unknown validation issue",
                    title_limit=TITLE_MAX_CHARS,
                    description_limit=DESCRIPTION_MAX_CHARS,
                )
                await self.event_repo.append(
                    job_id=job_id,
                    event_type=JobEventType.SEO_VALIDATED.value,
                    level=EventLevel.WARNING.value,
                    stage="REDUCTION",
                    message=f"SEO validation failed; issuing repair request {repair_attempt + 1}.",
                    payload={"issues": issues},
                )
                continue

            metadata["repair_attempts"] = repair_attempt
            await self.event_repo.append(
                job_id=job_id,
                event_type=JobEventType.SEO_VALIDATED.value,
                level=EventLevel.SUCCESS.value,
                stage="REDUCTION",
                message="SEO output validated against YouTube constraints.",
                payload={
                    "title_length": metadata.get("title_length"),
                    "description_length": metadata.get("description_length"),
                    "chapters": metadata.get("chapter_validation", {}).get("count"),
                    "warnings": metadata.get("warnings", []),
                },
            )
            return output, {**metadata, "raw_payload": raw_payload}, usage_totals

        raise last_error or SEOValidationError(
            "The generated SEO output could not be validated.",
            code=ErrorCode.SEO_VALIDATION_ERROR,
        )

    # --------------------------------------------------------------- internals
    async def _prepare_timeline(self, *, job_id: Any, timeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Compress the timeline hierarchically when it exceeds the safe budget."""
        estimated = estimate_reduce_input_tokens(timeline)
        if estimated <= settings.reduce_safe_input_tokens or len(timeline) <= 8:
            return timeline

        logger.info("reduce_hierarchical_compression topics=%s estimated_tokens=%s", len(timeline), estimated)
        await self.event_repo.append(
            job_id=job_id,
            event_type=JobEventType.REDUCE_STARTED.value,
            level=EventLevel.WARNING.value,
            stage="REDUCTION",
            message=(
                "The timeline is large; compressing it in groups before the final SEO request "
                "(hierarchical Reduce)."
            ),
            payload={"topics": len(timeline), "estimated_tokens": estimated},
        )

        group_size = max(6, len(timeline) // 6)
        compressed: list[dict[str, Any]] = []
        for start in range(0, len(timeline), group_size):
            group = timeline[start : start + group_size]
            compressed.extend(await self._compress_group(job_id=job_id, group=group))
        return compressed or timeline

    async def _compress_group(self, *, job_id: Any, group: list[dict[str, Any]]) -> list[dict[str, Any]]:
        start_seconds = min(float(item.get("start_seconds", 0)) for item in group)
        end_seconds = max(float(item.get("end_seconds", 0)) for item in group)
        prompt = (
            "Compress this section of a long video's content timeline into 3-6 meaningful topics.\n"
            "Preserve key topics, important keywords, meaningful timestamps and major section "
            "transitions. Do not lose chronology. Do not invent content.\n"
            f"Section time range: {start_seconds} - {end_seconds} seconds.\n"
            "Return JSON only, using the supplied schema, with timestamps in absolute seconds.\n\n"
            "TIMELINE SECTION:\n" + json.dumps(group, ensure_ascii=False)
        )

        async def _call(attempt: int):
            return await self.client.generate_structured(
                model=self.model,
                system_instruction=(
                    "You compress content timelines for a YouTube SEO pipeline. Output JSON only."
                ),
                user_prompt=prompt,
                schema=SUMMARY_SCHEMA,
                audio_file=None,
                thinking_level=settings.reduce_thinking_level,
            )

        response = await run_inference(
            call=_call,
            phase=AIRequestPhase.REDUCE_SUMMARY.value,
            model=self.model,
            estimated_input_tokens=(len(prompt) // 4) + 1000,
            job_id=job_id,
            ai_repo=self.ai_repo,
            limiter=self.limiter,
            max_retries=settings.max_gemini_retries,
        )

        topics = response.payload.get("topics") or []
        result: list[dict[str, Any]] = []
        for topic in topics:
            try:
                start = max(start_seconds, float(topic["start_seconds"]))
                end = min(end_seconds, float(topic["end_seconds"]))
            except (KeyError, TypeError, ValueError):
                continue
            if end <= start:
                continue
            result.append(
                {
                    "topic": str(topic.get("topic", "")).strip(),
                    "summary": str(topic.get("summary", "")).strip(),
                    "start_seconds": start,
                    "end_seconds": end,
                    "source_chunk_indices": [],
                }
            )
        return result or group


def _extract_issues(error: SEOValidationError) -> list[str]:
    details = error.details
    if isinstance(details, dict):
        issues = details.get("errors") or []
        if issues:
            return [str(issue) for issue in issues][:10]
        chapter = details.get("chapter_validation") or {}
        if chapter.get("issues"):
            return [str(issue) for issue in chapter["issues"]][:10]
    if isinstance(details, str):
        return [details[:400]]
    return [error.message]


__all__ = ["SEO_RESPONSE_SCHEMA", "SUMMARY_SCHEMA", "GeminiReduceService"]
