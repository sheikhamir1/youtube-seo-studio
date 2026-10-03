"""Time helpers: formatting, parsing and an injectable clock.

A clock abstraction keeps the rate limiter and retry logic unit-testable
without real sleeping (see ``tests/unit/test_rate_limiter.py``).
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Protocol

_CHAPTER_TIMESTAMP = r"(?P<h>\d{1,2}):(?P<m>\d{2}):(?P<s>\d{2})|(?P<m2>\d{1,3}):(?P<s2>\d{2})"


def utcnow() -> datetime:
    """Timezone-aware UTC now (all database timestamps are UTC)."""
    return datetime.now(UTC)


def format_duration(seconds: float | None) -> str:
    """Human-readable duration, e.g. ``14h 18m 04s`` / ``12m 04s``."""
    if seconds is None or seconds != seconds or seconds < 0:  # NaN guard
        return "unknown"
    total = round(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"


def format_timestamp(seconds: float) -> str:
    """Format seconds as a YouTube chapter / display timestamp.

    Under one hour:      ``00:00``, ``07:42``, ``59:59``
    One hour or more:    ``1:00:00``, ``1:17:42``, ``12:04:33``

    Seconds are rounded to the nearest whole second and the result is always
    well formed (never ``00:60``).
    """
    if seconds is None or seconds != seconds or seconds < 0:
        seconds = 0
    total = round(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def parse_timestamp(value: str) -> float | None:
    """Parse ``MM:SS`` / ``H:MM:SS`` into seconds; ``None`` when unparseable."""
    import re

    match = re.fullmatch(_CHAPTER_TIMESTAMP, value.strip())
    if not match:
        return None
    if match.group("h") is not None:
        hours = int(match.group("h"))
        minutes = int(match.group("m"))
        secs = int(match.group("s"))
    else:
        hours = 0
        minutes = int(match.group("m2"))
        secs = int(match.group("s2"))
    if minutes >= 60 or secs >= 60:
        return None
    return float(hours * 3600 + minutes * 60 + secs)


class Clock(Protocol):
    """Minimal clock protocol so tests can inject a fake clock."""

    def monotonic(self) -> float: ...

    def now(self) -> datetime: ...

    async def sleep(self, seconds: float) -> None: ...


class SystemClock:
    """Production clock: monotonic for pacing, UTC wall clock for records."""

    def monotonic(self) -> float:
        return time.monotonic()

    def now(self) -> datetime:
        return utcnow()

    async def sleep(self, seconds: float) -> None:
        import asyncio

        if seconds > 0:
            await asyncio.sleep(seconds)


def floor_seconds(value: float) -> int:
    """Deliberate, consistent chapter rounding: floor to whole seconds."""
    return int(value // 1)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
