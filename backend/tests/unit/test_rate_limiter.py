"""Rate limiter tests: pacing, restart safety, RPM/TPM/RPD (no real sleeping)."""

from __future__ import annotations

import pytest

from app.core.errors import ErrorCode, GeminiRateLimitError
from app.services.ai.rate_limiter import (
    GeminiRateLimiter,
    compute_backoff_seconds,
    compute_interval_wait,
)


def test_wait_when_only_20_seconds_elapsed():
    # last start 20 s ago, minimum interval 60 s => 40 s remaining.
    assert compute_interval_wait(
        now_monotonic=1000.0, last_start_monotonic=980.0, min_interval_seconds=60
    ) == pytest.approx(40.0)


def test_no_wait_when_80_seconds_elapsed():
    assert (
        compute_interval_wait(now_monotonic=1000.0, last_start_monotonic=920.0, min_interval_seconds=60)
        == 0.0
    )


def test_first_request_never_waits():
    assert (
        compute_interval_wait(now_monotonic=1000.0, last_start_monotonic=None, min_interval_seconds=60) == 0.0
    )


async def test_limiter_waits_between_request_starts(fake_clock, fake_history):
    limiter = GeminiRateLimiter(
        history=fake_history,
        clock=fake_clock,
        min_interval_seconds=60,
        rpm_limit=15,
        tpm_limit=250_000,
        rpd_limit=500,
    )
    await limiter.acquire(estimated_tokens=1000)
    limiter.release()

    # A request that took 75 s needs no extra wait: 75 > 60 between starts.
    fake_clock.advance(75)
    decision = await limiter.acquire(estimated_tokens=1000)
    limiter.release()
    assert decision.wait_seconds == 0.0

    # Only 18 s later, the limiter must wait the remaining 42 s.
    fake_clock.advance(18)
    decision = await limiter.acquire(estimated_tokens=1000)
    limiter.release()
    assert decision.wait_seconds == pytest.approx(42.0)
    assert fake_clock.sleeps[-1] == pytest.approx(42.0)


async def test_restart_safety_uses_persisted_history(fake_clock, fake_history):
    """After a restart the in-process timer is gone: the DB decides."""
    fake_history.record(fake_clock.now() - __import__("datetime").timedelta(seconds=20))
    limiter = GeminiRateLimiter(
        history=fake_history,
        clock=fake_clock,
        min_interval_seconds=60,
        rpm_limit=15,
        tpm_limit=250_000,
        rpd_limit=500,
    )
    decision = await limiter.acquire(estimated_tokens=1000)
    limiter.release()
    assert decision.wait_seconds == pytest.approx(40.0, abs=0.5)


async def test_rolling_rpm_protection(fake_clock, fake_history):
    for _ in range(15):
        fake_history.record(fake_clock.now())
    limiter = GeminiRateLimiter(
        history=fake_history,
        clock=fake_clock,
        min_interval_seconds=0,
        rpm_limit=15,
        tpm_limit=250_000,
        rpd_limit=500,
    )
    decision = await limiter.acquire(estimated_tokens=1000)
    limiter.release()
    assert decision.wait_seconds == 60.0
    assert "RPM" in decision.reason


async def test_rolling_tpm_protection(fake_clock, fake_history):
    fake_history.record(fake_clock.now(), tokens=245_000)
    limiter = GeminiRateLimiter(
        history=fake_history,
        clock=fake_clock,
        min_interval_seconds=0,
        rpm_limit=15,
        tpm_limit=250_000,
        rpd_limit=500,
    )
    decision = await limiter.acquire(estimated_tokens=100_000)
    limiter.release()
    assert decision.wait_seconds == 60.0
    assert "TPM" in decision.reason


async def test_daily_budget_raises(fake_clock, fake_history):
    for _ in range(500):
        fake_history.record(fake_clock.now())
    limiter = GeminiRateLimiter(
        history=fake_history,
        clock=fake_clock,
        min_interval_seconds=0,
        rpm_limit=15,
        tpm_limit=250_000,
        rpd_limit=500,
    )
    with pytest.raises(GeminiRateLimitError) as excinfo:
        await limiter.acquire(estimated_tokens=1000)
    assert excinfo.value.code == ErrorCode.GEMINI_RATE_LIMIT


async def test_concurrency_is_one_by_default(fast_limiter):
    await fast_limiter.acquire(estimated_tokens=1000)
    assert fast_limiter._semaphore.locked() is True
    fast_limiter.release()
    assert fast_limiter._semaphore.locked() is False


async def test_quota_snapshot_reports_application_tracked_usage(fake_clock, fake_history):
    fake_history.record(fake_clock.now(), tokens=1200)
    limiter = GeminiRateLimiter(
        history=fake_history,
        clock=fake_clock,
        min_interval_seconds=45,
        rpm_limit=15,
        tpm_limit=250_000,
        rpd_limit=500,
    )
    snapshot = await limiter.snapshot(estimated_next_tokens=115_200)
    assert snapshot["requests_today"] == 1
    assert snapshot["rolling_minute_tokens"] == 1200
    assert snapshot["estimated_next_request_tokens"] == 115_200
    # Below-default pacing must be surfaced as a warning, never silently applied.
    assert snapshot["warning"] == "Less conservative than the default free-tier pacing."


def test_backoff_prefers_retry_after():
    delay = compute_backoff_seconds(1, base=2.0, maximum=300.0, retry_after=30.0, jitter=0.0)
    assert delay == pytest.approx(30.0)


def test_backoff_is_exponential_and_capped():
    assert compute_backoff_seconds(1, base=2.0, maximum=300.0, jitter=0.0) == 2.0
    assert compute_backoff_seconds(2, base=2.0, maximum=300.0, jitter=0.0) == 4.0
    assert compute_backoff_seconds(3, base=2.0, maximum=300.0, jitter=0.0) == 8.0
    assert compute_backoff_seconds(12, base=2.0, maximum=300.0, jitter=0.0) == 300.0
