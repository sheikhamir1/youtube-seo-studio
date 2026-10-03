"""Shared inference flow: pacing, request logging, retries and backoff.

Every Gemini call in the application goes through :func:`run_inference` so that
pacing, quota accounting and error classification can never drift apart.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.core.constants import BACKOFF_BASE_SECONDS, BACKOFF_MAX_SECONDS
from app.core.errors import ErrorCode, GeminiError
from app.core.logging import get_logger
from app.repositories.ai_requests import AIRequestRepository
from app.services.ai.client import StructuredResponse, classify_exception, retry_after_seconds
from app.services.ai.rate_limiter import GeminiRateLimiter, compute_backoff_seconds

logger = get_logger(__name__)


class NonRetryableInferenceError(GeminiError):
    """Raised when the provider reported a permanent problem."""


@dataclass
class AttemptOutcome:
    attempt: int
    error_code: str | None = None
    message: str | None = None
    retryable: bool = False
    retry_after: float | None = None
    http_status: int | None = None


async def run_inference(
    *,
    call: Callable[[int], Awaitable[StructuredResponse]],
    phase: str,
    model: str,
    estimated_input_tokens: int,
    job_id: Any,
    audio_chunk_id: Any = None,
    ai_repo: AIRequestRepository | None = None,
    limiter: GeminiRateLimiter,
    max_retries: int = 8,
    backoff_base_seconds: float = BACKOFF_BASE_SECONDS,
    backoff_max_seconds: float = BACKOFF_MAX_SECONDS,
    on_retry: Callable[[AttemptOutcome], Awaitable[None] | None] | None = None,
    should_abort: Callable[[], bool] | None = None,
) -> StructuredResponse:
    """Execute one inference request with pacing and bounded retries.

    Retry policy: 429/5xx/timeouts/connection resets are retried with
    exponential backoff + jitter and the provider's Retry-After hint when
    available. Authentication failures, invalid models, invalid requests and
    safety blocks fail immediately. Every attempt is logged and counted against
    the configured budget (retries are never hidden).
    """
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 2):
        if should_abort and should_abort():
            raise GeminiError(
                "Inference aborted because the job was canceled.",
                code=ErrorCode.JOB_CANCELED,
                http_status=409,
            )

        # Pacing is enforced for every attempt, including retries.
        await limiter.acquire(estimated_tokens=estimated_input_tokens)
        log_record = None
        if ai_repo is not None:
            log_record = await ai_repo.start(
                job_id=job_id,
                audio_chunk_id=audio_chunk_id,
                model=model,
                phase=phase,
                attempt_number=attempt,
                estimated_input_tokens=estimated_input_tokens,
            )
        started = time.monotonic()

        try:
            response = await call(attempt)
        except Exception as exc:
            limiter.release()
            latency_ms = (time.monotonic() - started) * 1000
            code, status, retryable = classify_exception(exc)
            last_error = exc

            if log_record is not None and ai_repo is not None:
                await ai_repo.finish_failure(
                    log_record.id,
                    status="RATE_LIMITED" if code == ErrorCode.GEMINI_RATE_LIMIT else "FAILED",
                    error_code=code,
                    error_message=str(exc)[:500],
                    http_status_code=status,
                    latency_ms=latency_ms,
                )

            outcome = AttemptOutcome(
                attempt=attempt,
                error_code=code,
                message=str(exc)[:400],
                retryable=retryable,
                retry_after=retry_after_seconds(exc),
                http_status=status,
            )
            if on_retry:
                maybe_awaitable = on_retry(outcome)
                if maybe_awaitable is not None:
                    await maybe_awaitable

            if not retryable or attempt > max_retries:
                raise _wrap_error(code, status, str(exc), attempt) from exc

            delay = compute_backoff_seconds(
                attempt,
                base=backoff_base_seconds,
                maximum=backoff_max_seconds,
                retry_after=outcome.retry_after,
            )
            logger.warning(
                "gemini_retry attempt=%s code=%s delay=%.1fs message=%s",
                attempt,
                code,
                delay,
                str(exc)[:200],
            )
            import asyncio

            await asyncio.sleep(delay)
            continue

        # Success: capture real usage when the SDK exposes it.
        limiter.release()
        latency_ms = (time.monotonic() - started) * 1000
        if log_record is not None and ai_repo is not None:
            usage = response.usage
            await ai_repo.finish_success(
                log_record.id,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                total_tokens=usage.total_tokens,
                thinking_tokens=usage.thinking_tokens,
                latency_ms=latency_ms,
            )
        logger.info(
            "gemini_request_success phase=%s attempt=%s latency_ms=%.0f tokens=%s",
            phase,
            attempt,
            latency_ms,
            response.usage.total_tokens,
        )
        return response

    raise GeminiError(
        "Gemini request failed after all retry attempts.",
        code=ErrorCode.GEMINI_TRANSIENT_ERROR,
        details={"last_error": str(last_error)[:400] if last_error else None},
    )


def _wrap_error(code: str, status: int | None, message: str, attempt: int) -> GeminiError:
    from app.core.errors import (
        GeminiAuthError,
        GeminiRateLimitError,
        GeminiSafetyBlockError,
        GeminiSchemaError,
    )

    details = {"message": message[:500], "attempts": attempt}
    if code == ErrorCode.GEMINI_RATE_LIMIT:
        return GeminiRateLimitError("Gemini rate limit persisted after retry attempts.", details=details)
    if code == ErrorCode.GEMINI_AUTH_ERROR:
        return GeminiAuthError(
            "Gemini authentication failed. Check GEMINI_API_KEY in your .env file.", details=details
        )
    if code == ErrorCode.GEMINI_SAFETY_BLOCK:
        return GeminiSafetyBlockError(
            "Gemini refused to process this content (safety block).", details=details
        )
    if code == ErrorCode.GEMINI_SCHEMA_ERROR:
        return GeminiSchemaError("Gemini returned data that failed validation.", details=details)
    return GeminiError(
        "Gemini request failed.",
        code=code,
        http_status=status or 502,
        details=details,
    )
