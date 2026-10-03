"""Token estimation helpers (planning only - never presented as billing data)."""

from __future__ import annotations

import json
from typing import Any

from app.core.config import settings
from app.core.timeutils import format_duration
from app.services.media.chunking import count_chunks, estimate_audio_tokens


def estimate_chunk_input_tokens(
    duration_seconds: float,
    *,
    system_prompt: str = "",
    user_prompt: str = "",
    tokens_per_second: float | None = None,
) -> int:
    """Estimated request cost for one Map call.

    The estimate covers audio + instructions + a generation allowance; the exact
    provider value is stored separately once Gemini reports real usage.
    """
    audio_tokens = estimate_audio_tokens(
        duration_seconds, tokens_per_second=tokens_per_second or settings.audio_tokens_per_second
    )
    instruction_tokens = (len(system_prompt) + len(user_prompt)) // 4
    # Allowance for the structured JSON response (topics + summaries).
    generation_allowance = 1500
    return audio_tokens + instruction_tokens + generation_allowance


def estimate_reduce_input_tokens(timeline: list[dict[str, Any]], *, instruction_chars: int = 4000) -> int:
    """Estimated Reduce request cost from the normalized timeline size."""
    timeline_chars = len(json.dumps(timeline, ensure_ascii=False))
    return (timeline_chars + instruction_chars) // 4 + 2000


def build_preflight(
    *,
    duration_seconds: float | None,
    chunk_duration_seconds: float,
    chunk_overlap_seconds: float,
    requests_today: int,
    rpd_limit: int,
    chunk_estimate_tokens: int,
) -> dict[str, Any]:
    """Preflight estimate shown before a job starts (honest, non-guaranteed)."""
    if not duration_seconds:
        return {
            "duration_seconds": duration_seconds,
            "duration_formatted": "unknown",
            "estimated_chunks": 0,
            "estimated_map_requests": 0,
            "estimated_reduce_requests": 1,
            "estimated_total_requests": 1,
            "estimated_input_tokens_per_chunk": chunk_estimate_tokens,
            "estimated_total_tokens": chunk_estimate_tokens,
            "requests_today": requests_today,
            "rpd_limit": rpd_limit,
            "exceeds_daily_budget": False,
            "warning": "Duration unknown: run validation first for an accurate estimate.",
        }

    chunk_count = count_chunks(
        duration_seconds, chunk_duration=chunk_duration_seconds, overlap=chunk_overlap_seconds
    )
    reduce_requests = 1
    total_requests = chunk_count + reduce_requests
    total_tokens = chunk_estimate_tokens * chunk_count + 6000

    warning = None
    if requests_today + total_requests > rpd_limit:
        warning = (
            "Estimated request usage is high compared with the configured daily Gemini request budget. "
            f"This job needs about {total_requests} requests and {requests_today} have already been logged today."
        )

    return {
        "duration_seconds": duration_seconds,
        "duration_formatted": format_duration(duration_seconds),
        "estimated_chunks": chunk_count,
        "estimated_map_requests": chunk_count,
        "estimated_reduce_requests": reduce_requests,
        "estimated_total_requests": total_requests,
        "estimated_input_tokens_per_chunk": chunk_estimate_tokens,
        "estimated_total_tokens": total_tokens,
        "requests_today": requests_today,
        "rpd_limit": rpd_limit,
        "exceeds_daily_budget": requests_today + total_requests > rpd_limit,
        "warning": warning,
    }
