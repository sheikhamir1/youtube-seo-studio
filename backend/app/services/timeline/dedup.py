"""Deterministic overlap deduplication for chunk Map results.

Adjacent chunks overlap by design (default 60 s), so the same topic can appear
in two results. We resolve that locally - never with an extra Gemini request.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

try:  # RapidFuzz is preferred when available (much faster).
    from rapidfuzz import fuzz as _fuzz  # type: ignore

    def similarity(a: str, b: str) -> float:
        return float(_fuzz.token_set_ratio(a, b)) / 100.0

except Exception:  # pragma: no cover - fallback path

    def similarity(a: str, b: str) -> float:
        return SequenceMatcher(None, a, b).ratio()


_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_WHITESPACE = re.compile(r"\s+")

# Short connector words are noise when comparing topic strings.
_STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "to",
    "in",
    "on",
    "for",
    "with",
    "how",
    "what",
    "why",
    "is",
    "are",
    "introduction",
    "intro",
    "part",
    "section",
}


def normalize_topic_string(value: str) -> str:
    """Lowercase, strip punctuation and drop pure filler words for comparison."""
    text = _PUNCT.sub(" ", (value or "").casefold())
    words = [word for word in _WHITESPACE.split(text) if word]
    meaningful = [word for word in words if word not in _STOPWORDS]
    return " ".join(meaningful or words)


def topics_are_duplicates(
    left: dict[str, Any],
    right: dict[str, Any],
    *,
    threshold: float,
    proximity_seconds: float,
) -> tuple[bool, float]:
    """Decide whether two timeline entries describe the same topic.

    Requires BOTH a high text similarity and temporal proximity/overlap, so
    genuinely different adjacent topics are never merged by accident.
    """
    left_topic = normalize_topic_string(str(left.get("topic", "")))
    right_topic = normalize_topic_string(str(right.get("topic", "")))
    topic_score = similarity(left_topic, right_topic) if left_topic and right_topic else 0.0

    left_summary = normalize_topic_string(str(left.get("summary", "")))
    right_summary = normalize_topic_string(str(right.get("summary", "")))
    summary_score = similarity(left_summary, right_summary) if left_summary and right_summary else 0.0

    # Combined score: topic text dominates, summary supports the decision.
    score = max(topic_score, (topic_score * 0.7) + (summary_score * 0.3))

    temporal = _temporally_close(left, right, proximity_seconds=proximity_seconds)
    return (score >= threshold and temporal), score


def _temporally_close(left: dict[str, Any], right: dict[str, Any], *, proximity_seconds: float) -> bool:
    l_start, l_end = float(left.get("start_seconds", 0)), float(left.get("end_seconds", 0))
    r_start, r_end = float(right.get("start_seconds", 0)), float(right.get("end_seconds", 0))
    overlap = min(l_end, r_end) - max(l_start, r_start)
    if overlap > 0:
        return True
    gap = max(l_start, r_start) - min(l_end, r_end)
    return gap <= proximity_seconds


def merge_topics(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Merge two duplicate entries.

    start = minimum start, end = maximum end, the more informative summary wins
    and the unique source chunk indices are combined.
    """
    start = min(float(left.get("start_seconds", 0)), float(right.get("start_seconds", 0)))
    end = max(float(left.get("end_seconds", 0)), float(right.get("end_seconds", 0)))

    left_summary = str(left.get("summary", "") or "")
    right_summary = str(right.get("summary", "") or "")
    summary = right_summary if len(right_summary) > len(left_summary) else left_summary

    left_topic = str(left.get("topic", "") or "")
    right_topic = str(right.get("topic", "") or "")
    # Prefer the more descriptive label, but keep the earlier one on ties.
    if len(right_topic) > len(left_topic) * 1.5:
        topic = right_topic
    else:
        topic = left_topic or right_topic

    sources = sorted(
        {
            int(index)
            for index in list(left.get("source_chunk_indices") or [])
            + list(right.get("source_chunk_indices") or [])
        }
    )
    return {
        "topic": topic,
        "summary": summary,
        "start_seconds": start,
        "end_seconds": end,
        "source_chunk_indices": sources,
    }
