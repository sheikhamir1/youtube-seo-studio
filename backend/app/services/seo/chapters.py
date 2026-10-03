"""Chapter parsing, deterministic repair and validation.

Chapter timestamps must come from real content timing (the normalized
timeline); the model is never trusted blindly.
"""

from __future__ import annotations

import re
from typing import Any

from app.core.constants import (
    MIN_CHAPTER_SPACING_SECONDS,
    MIN_CHAPTERS_LONG_FORM,
    TIMESTAMP_EPSILON_SECONDS,
)
from app.core.timeutils import format_timestamp, parse_timestamp

# A chapter may sit within this distance of a real timeline topic start.
GROUNDING_TOLERANCE_SECONDS = 90.0
# Tolerance for a chapter that lands a few seconds outside a topic window.
WINDOW_PADDING = 5.0

# Dashes accepted as separators: ASCII hyphen, en dash (\u2013) and em dash (\u2014).
# Matches "00:00 Title", "1:02:03 - Title", "12:04:33 - Title"
CHAPTER_LINE = re.compile(
    r"^\s*(?P<ts>\d{1,2}:\d{2}:\d{2}|\d{1,3}:\d{2})\s*(?:[-\u2013\u2014:.)]\s*)?(?P<title>\S.*)?$"
)
# Simple typo repair: "00:0" -> "00:00" (missing second digit).
SHORT_SECONDS = re.compile(r"^\s*(?P<m>\d{1,3}):(?P<s>\d)\s*(?:[-\u2013\u2014:.)]\s*)?(?P<title>.*)$")
# Structurally a timestamp, but with an impossible minutes/seconds value.
IMPOSSIBLE_TIMESTAMP = re.compile(
    r"^\s*(?:(?P<h>\d{1,2}):)?(?P<m>\d{1,3}):(?P<s>\d{2})\s*(?:[-\u2013\u2014:.)]\s*)?(?P<title>\S.*)?$"
)


def find_impossible_timestamps(description: str) -> list[str]:
    """Return chapter-looking lines whose minute/second value cannot exist."""
    problems: list[str] = []
    for line in (description or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = IMPOSSIBLE_TIMESTAMP.match(stripped)
        if not match:
            continue
        minutes = int(match.group("m"))
        seconds = int(match.group("s"))
        if minutes >= 60 or seconds >= 60:
            problems.append(stripped)
    return problems


def extract_chapters(description: str) -> list[dict[str, Any]]:
    """Extract chapter entries from a description body.

    Titles are preserved verbatim (including Devanagari / Arabic script).
    """
    chapters: list[dict[str, Any]] = []
    for raw_line in (description or "").splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        match = CHAPTER_LINE.match(line)
        if match:
            seconds = parse_timestamp(match.group("ts"))
            if seconds is None:
                continue
            title = (match.group("title") or "").strip(" -\u2013\u2014:.")
            chapters.append(
                {
                    "seconds": seconds,
                    "timestamp": format_timestamp(seconds),
                    "title": title,
                    "line": line,
                }
            )
    return chapters


def repair_description_chapters(description: str) -> tuple[str, list[str]]:
    """Apply only safe, deterministic repairs. Returns (text, applied repairs)."""
    repairs: list[str] = []
    lines = (description or "").splitlines()
    repaired: list[str] = []

    for line in lines:
        fixed = line
        short = SHORT_SECONDS.match(line)
        if short and not CHAPTER_LINE.match(line.strip()):
            # "00:0 Topic" -> "00:00 Topic": a pure formatting typo.
            minutes = short.group("m").zfill(2)
            seconds = f"{short.group('s')}0"
            title = short.group("title").strip()
            fixed = f"{minutes}:{seconds}" + (f" {title}" if title else "")
            repairs.append(f"normalized short timestamp: '{line.strip()}' -> '{fixed.strip()}'")
        repaired.append(fixed)

    text = "\n".join(repaired)

    # Remove duplicate identical timestamps (keep the first).
    seen: set[str] = set()
    deduped: list[str] = []
    for line in text.splitlines():
        match = CHAPTER_LINE.match(line)
        if match:
            ts = format_timestamp(parse_timestamp(match.group("ts")) or 0)
            if ts in seen:
                repairs.append(f"removed duplicate chapter timestamp {ts}")
                continue
            seen.add(ts)
        deduped.append(line)
    text = "\n".join(deduped)

    # Sort chapters if the semantic order is otherwise unchanged (all lines are
    # chapter lines and they are simply out of order).
    chapter_lines = [line for line in text.splitlines() if CHAPTER_LINE.match(line)]
    if len(chapter_lines) >= 2 and len(chapter_lines) == len(
        [line for line in text.splitlines() if line.strip()]
    ):
        parsed = [
            (parse_timestamp(CHAPTER_LINE.match(line).group("ts")) or 0.0, line) for line in chapter_lines
        ]
        ordered = sorted(parsed, key=lambda item: item[0])
        if [item[1] for item in ordered] != chapter_lines:
            repairs.append("sorted chapter timestamps chronologically")
            text = "\n".join(line for _, line in ordered)

    return text, repairs


def validate_chapters(
    description: str,
    *,
    video_duration_seconds: float | None,
    allowed_timestamps: list[float] | None = None,
    allowed_windows: list[tuple[float, float]] | None = None,
) -> dict[str, Any]:
    """Validate YouTube chapter rules and return a metadata report.

    ``allowed_windows`` are the real timeline topic ranges; a chapter timestamp is
    "grounded" when it falls inside one of those ranges (with a small padding) or
    sits within the tolerance of a topic start. Chapters invented by the model
    are therefore rejected rather than trusted.
    """
    chapters = extract_chapters(description)
    checks: dict[str, bool] = {}
    issues: list[str] = []

    impossible = find_impossible_timestamps(description)
    checks["timestamps_parseable"] = not impossible
    if impossible:
        issues.append("Impossible chapter timestamp(s) found: " + ", ".join(impossible[:3]))

    checks["starts_at_zero"] = bool(chapters) and abs(chapters[0]["seconds"]) < 1.0
    if not checks["starts_at_zero"]:
        issues.append("The first chapter timestamp must be 00:00.")

    seconds = [chapter["seconds"] for chapter in chapters]
    checks["chronological"] = (
        all(seconds[i] < seconds[i + 1] for i in range(len(seconds) - 1))
        if len(seconds) > 1
        else bool(seconds)
    )
    if not checks["chronological"]:
        issues.append("Chapter timestamps must be strictly ascending.")

    checks["minimum_count"] = len(chapters) >= MIN_CHAPTERS_LONG_FORM
    if not checks["minimum_count"]:
        issues.append(f"Long-form content requires at least {MIN_CHAPTERS_LONG_FORM} chapters.")

    checks["spacing_valid"] = (
        all(seconds[i + 1] - seconds[i] >= MIN_CHAPTER_SPACING_SECONDS for i in range(len(seconds) - 1))
        if len(seconds) > 1
        else True
    )
    if not checks["spacing_valid"]:
        issues.append(
            f"Chapter timestamps must be at least {int(MIN_CHAPTER_SPACING_SECONDS)} seconds apart."
        )

    within_duration = True
    if video_duration_seconds:
        within_duration = all(
            second <= video_duration_seconds + TIMESTAMP_EPSILON_SECONDS for second in seconds
        )
    checks["within_duration"] = within_duration
    if not within_duration:
        issues.append("A chapter timestamp exceeds the video duration.")

    checks["titles_present"] = all(chapter["title"] for chapter in chapters)
    if not checks["titles_present"]:
        issues.append("Every chapter needs a title.")

    grounded = True
    if allowed_windows or allowed_timestamps:
        windows = list(allowed_windows or [])
        starts = sorted(allowed_timestamps or [])
        for second in seconds:
            if windows and any(
                start - WINDOW_PADDING <= second <= end + WINDOW_PADDING for start, end in windows
            ):
                continue
            if any(abs(second - start) <= GROUNDING_TOLERANCE_SECONDS for start in starts):
                continue
            grounded = False
            issues.append(
                f"Chapter timestamp {format_timestamp(second)} does not map to the supplied timeline."
            )
            break
    checks["timestamps_grounded"] = grounded

    valid = all(checks.values())
    return {
        "valid": valid,
        "chapters": chapters,
        "checks": checks,
        "issues": issues,
    }
