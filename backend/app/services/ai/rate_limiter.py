"""GeminiRateLimiter: pacing, concurrency, RPM/TPM and daily budget.

Rules implemented (see spec sections 4-6):
1. at most one Gemini inference request at a time;
2. a minimum interval measured between request **start** times;
3. rolling RPM protection;
4. rolling TPM protection;
5. daily request budget tracking (retries included);
6. restart safety: recent request history is read from PostgreSQL.

The limiter never sleeps 60 s blindly after each request: it computes the
remaining time needed to respect the interval.
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol

from app.core.config import settings
from app.core.errors import ErrorCode, GeminiRateLimitError
from app.core.logging import get_logger
from app.core.timeutils import Clock, SystemClock

logger = get_logger(__name__)


class RequestHistory(Protocol):
    """Read access to persisted AI request history (implemented by the repo)."""

    async def last_request_start(self):  # -> datetime | None
        ...

    async def requests_since(self, since) -> int: ...

    async def tokens_since(self, since) -> int: ...


class NullHistory:
    """In-memory/first-run history: nothing has been requested yet."""

    async def last_request_start(self):
        return None

    async def requests_since(self, since) -> int:
        return 0

    async def tokens_since(self, since) -> int:
        return 0


@dataclass
class RateLimitDecision:
    """Result of a limiter check (used by tests and diagnostics)."""

    wait_seconds: float
    reason: str


def compute_interval_wait(
    *,
    now_monotonic: float,
    last_start_monotonic: float | None,
    min_interval_seconds: float,
) -> float:
    """Seconds still required before the next request may start.

    The minimum interval is measured between inference start times, avoiding
    unnecessary extra delay when a request itself takes longer than the
    configured interval.

    >>> compute_interval_wait(now_monotonic=1000.0, last_start_monotonic=980.0, min_interval_seconds=60)
    40.0
    >>> compute_interval_wait(now_monotonic=1000.0, last_start_monotonic=920.0, min_interval_seconds=60)
    0.0
    """
    if last_start_monotonic is None:
        return 0.0
    elapsed = now_monotonic - last_start_monotonic
    return max(0.0, min_interval_seconds - elapsed)


def compute_backoff_seconds(
    attempt: int,
    *,
    base: float,
    maximum: float,
    retry_after: float | None = None,
    jitter: float = 0.25,
) -> float:
    """Exponential backoff with jitter, honouring provider Retry-After."""
    if retry_after is not None and retry_after > 0:
        return min(maximum, retry_after + random.uniform(0, jitter * 2))
    exponential = base * (2 ** max(0, attempt - 1))
    capped = min(maximum, exponential)
    return capped + random.uniform(0, capped * jitter)


class GeminiRateLimiter:
    """Serialises Gemini inference and enforces pacing + quota budgets."""

    def __init__(
        self,
        *,
        history: RequestHistory | None = None,
        clock: Clock | None = None,
        max_concurrency: int | None = None,
        min_interval_seconds: float | None = None,
        rpm_limit: int | None = None,
        tpm_limit: int | None = None,
        rpd_limit: int | None = None,
    ) -> None:
        self.history = history or NullHistory()
        self.clock = clock or SystemClock()
        self.max_concurrency = max_concurrency or settings.gemini_max_concurrency
        self.min_interval_seconds = (
            settings.gemini_min_interval_seconds if min_interval_seconds is None else min_interval_seconds
        )
        self.rpm_limit = rpm_limit or settings.gemini_rpm_limit
        self.tpm_limit = tpm_limit or settings.gemini_tpm_limit
        self.rpd_limit = rpd_limit or settings.gemini_rpd_limit

        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(max(1, self.max_concurrency))
        # Monotonic timestamp of the last request start observed in this process.
        self._last_start_monotonic: float | None = None
        self._last_error: RateLimitDecision | None = None

    # ------------------------------------------------------------------ public
    async def acquire(self, *, estimated_tokens: int, job_id: str | None = None) -> RateLimitDecision:
        """Wait until a request may start. Call immediately before inferencing."""
        async with self._lock:
            decision = await self._compute_decision(estimated_tokens=estimated_tokens)
            if decision.wait_seconds > 0:
                logger.info(
                    "rate_limiter_wait seconds=%.1f reason=%s", decision.wait_seconds, decision.reason
                )
                await self.clock.sleep(decision.wait_seconds)
            await self._semaphore.acquire()
            self._last_start_monotonic = self.clock.monotonic()
            self._last_error = None
            return RateLimitDecision(wait_seconds=decision.wait_seconds, reason=decision.reason)

    def release(self) -> None:
        """Release the concurrency slot once an inference call has finished."""
        if self._semaphore.locked():
            self._semaphore.release()

    async def __aenter__(self) -> GeminiRateLimiter:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        self.release()

    # --------------------------------------------------------------- internal
    async def _compute_decision(self, *, estimated_tokens: int) -> RateLimitDecision:
        waits: list[tuple[float, str]] = []

        # 1) minimum interval between request start times (in-process, monotonic).
        waits.append(
            (
                compute_interval_wait(
                    now_monotonic=self.clock.monotonic(),
                    last_start_monotonic=self._last_start_monotonic,
                    min_interval_seconds=self.min_interval_seconds,
                ),
                "minimum interval",
            )
        )

        # 2) restart safety: after a restart the in-process value is unknown, so
        #    the persisted history decides how long to wait.
        if self._last_start_monotonic is None:
            last_db_start = await self.history.last_request_start()
            if last_db_start is not None:
                elapsed = (self.clock.now() - last_db_start).total_seconds()
                waits.append((max(0.0, self.min_interval_seconds - elapsed), "persisted interval"))

        # 3) rolling RPM protection.
        minute_ago = self.clock.now() - timedelta(seconds=60)
        recent_requests = await self.history.requests_since(minute_ago)
        if self.rpm_limit and recent_requests >= self.rpm_limit:
            waits.append((60.0, f"rolling RPM limit ({recent_requests}/{self.rpm_limit})"))

        # 4) rolling TPM protection.
        recent_tokens = await self.history.tokens_since(minute_ago)
        if self.tpm_limit and recent_tokens + estimated_tokens > self.tpm_limit:
            waits.append(
                (
                    60.0,
                    f"rolling TPM limit ({recent_tokens}+{estimated_tokens}/{self.tpm_limit})",
                )
            )

        # 5) daily budget: every attempt counts, retries included.
        start_of_day = self.clock.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_requests = await self.history.requests_since(start_of_day)
        if self.rpd_limit and today_requests >= self.rpd_limit:
            raise GeminiRateLimitError(
                "The configured daily Gemini request budget has been reached. "
                "Increase GEMINI_RPD_LIMIT or wait until the next day.",
                details={"requests_today": today_requests, "rpd_limit": self.rpd_limit},
                code=ErrorCode.GEMINI_RATE_LIMIT,
            )

        wait_seconds, reason = max(waits, key=lambda item: item[0])
        return RateLimitDecision(wait_seconds=wait_seconds, reason=reason)

    # ------------------------------------------------------------------ report
    async def snapshot(self, *, estimated_next_tokens: int | None = None) -> dict[str, object]:
        """Quota dashboard payload - application-tracked usage only."""
        now = self.clock.now()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        requests_today = await self.history.requests_since(start_of_day)
        rolling_requests = await self.history.requests_since(now - timedelta(seconds=60))
        rolling_tokens = await self.history.tokens_since(now - timedelta(seconds=60))
        warning = None
        if self.min_interval_seconds < 60:
            warning = "Less conservative than the default free-tier pacing."
        return {
            "requests_today": requests_today,
            "rpd_limit": self.rpd_limit,
            "rolling_minute_requests": rolling_requests,
            "rpm_limit": self.rpm_limit,
            "rolling_minute_tokens": rolling_tokens,
            "tpm_limit": self.tpm_limit,
            "min_interval_seconds": self.min_interval_seconds,
            "estimated_next_request_tokens": estimated_next_tokens,
            "daily_budget_reached": bool(self.rpd_limit and requests_today >= self.rpd_limit),
            "warning": warning,
        }
