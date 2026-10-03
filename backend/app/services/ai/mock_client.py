"""Deterministic mock Gemini client (``AI_PROVIDER=mock``).

Used by tests and E2E runs so the suite never consumes real free-tier quota.
Responses are deterministic and always schema-valid, and they are clearly
labelled as mock data in the processing log.
"""

from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path
from typing import Any

from app.services.ai.client import StructuredResponse, UploadedFile, UsageMetadata

_TOPIC_LIBRARY = (
    "Introduction and session overview",
    "Core concepts and terminology",
    "Why this topic matters in practice",
    "Step-by-step worked example",
    "Common mistakes and how to avoid them",
    "Tools and workflow walkthrough",
    "Performance and quality trade-offs",
    "Case study discussion",
    "Questions from participants",
    "Summary and next steps",
)


class MockGeminiClient:
    """Returns deterministic structured data driven by the requested duration."""

    def __init__(self) -> None:
        self.deleted_files: list[str] = []
        self.uploaded_files: list[str] = []

    @property
    def provider_name(self) -> str:
        return "mock"

    async def upload_file(self, path: Path, *, mime_type: str | None = None) -> UploadedFile:
        self.uploaded_files.append(str(path))
        digest = hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:16]
        return UploadedFile(
            name=f"files/mock-{digest}",
            uri=f"https://mock.gemini.local/files/mock-{digest}",
            mime_type=mime_type or "audio/flac",
            state="ACTIVE",
        )

    async def wait_until_ready(self, file: UploadedFile) -> UploadedFile:
        file.state = "ACTIVE"
        return file

    async def generate_structured(
        self,
        *,
        model: str,
        system_instruction: str,
        user_prompt: str,
        schema: dict[str, Any],
        audio_file: UploadedFile | None = None,
        thinking_level: str | None = None,
    ) -> StructuredResponse:
        if "topics" in (schema.get("properties") or {}):
            payload = self._map_payload(user_prompt)
            estimated = 12_000
        else:
            payload = self._seo_payload(user_prompt)
            estimated = 5_000
        return StructuredResponse(
            payload=payload,
            usage=UsageMetadata(
                input_tokens=estimated,
                output_tokens=estimated // 4,
                total_tokens=estimated + estimated // 4,
            ),
            raw_text="[mock]",
            finish_reason="STOP",
        )

    async def delete_file(self, file: UploadedFile) -> None:
        self.deleted_files.append(file.name)

    # -------------------------------------------------------------- internals
    def _map_payload(self, user_prompt: str) -> dict[str, Any]:
        duration = _extract_number(user_prompt, "Chunk duration:", default=3600.0)
        index = int(_extract_number(user_prompt, "Chunk index:", default=0.0))
        topic_count = max(2, min(6, int(duration // 600) or 2))
        span = duration / topic_count

        topics = []
        for position in range(topic_count):
            start = round(position * span, 2)
            end = round(min(duration, start + span * 0.95), 2)
            if end <= start:
                end = start + 1.0
            label = _TOPIC_LIBRARY[(index * 3 + position) % len(_TOPIC_LIBRARY)]
            topics.append(
                {
                    "topic": label,
                    "summary": (
                        f"Mock analysis segment {position + 1} of chunk {index}: the speaker develops "
                        f"'{label.lower()}' with practical detail."
                    ),
                    "start_seconds": start,
                    "end_seconds": end,
                }
            )
        return {"topics": topics}

    def _seo_payload(self, user_prompt: str) -> dict[str, Any]:
        title = _extract_line(user_prompt, "VIDEO TITLE:") or "Long-Form Video Analysis"
        duration_seconds = _extract_number(user_prompt, "seconds)")
        topics = _extract_timeline_topics(user_prompt)

        chapters = ["00:00 Introduction"]
        seen = {0.0}
        for topic in topics[:24]:
            seconds = float(topic.get("start_seconds", 0))
            if any(abs(seconds - existing) < 10 for existing in seen):
                continue
            if duration_seconds and seconds > duration_seconds:
                continue
            seen.add(seconds)
            chapters.append(f"{_format_timestamp(seconds)} {str(topic.get('topic', '')).strip()}")
        if len(chapters) < 3:
            fallback = max(1.0, (duration_seconds or 180.0) / 3)
            chapters = [
                "00:00 Introduction",
                f"{_format_timestamp(fallback)} Main discussion",
                f"{_format_timestamp(fallback * 2)} Summary and next steps",
            ]

        description = (
            f"{title}\n\n"
            "This session walks through the main themes in order, with practical explanation and "
            "worked examples.\n\n"
            "Chapters:\n" + "\n".join(chapters) + "\n\n"
            "Generated by YouTube SEO Studio in mock AI mode for testing purposes."
        )[:4900]

        return {
            "title": title[:95],
            "description": description,
            "tags": [
                "long form video",
                "educational",
                "tutorial",
                "full course",
                "explained",
            ],
            "seo_score": 84,
            "improvement_suggestions": (
                "Mock mode suggestion: add a short hook in the first two description lines and keep "
                "chapter titles under 50 characters."
            ),
            "thumbnail_prompt": (
                "16:9 YouTube thumbnail, cinematic three-point lighting, a presenter at a desk with "
                "two subtle screen overlays, dark slate background with an indigo accent, bold "
                "readable title area on the left third, shallow depth of field, professional editorial "
                "look, no exaggerated facial expressions."
            ),
        }


_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _extract_number(text: str, marker: str, default: float = 0.0) -> float:
    """Read the numeric value that follows ``marker``.

    Prompts render values on the line *after* the label (``Chunk duration:``
    then the value), so both the inline and the next-line form are supported.
    Parsing the first number with a regex also avoids the classic bug of
    concatenating every digit on the line (``"1 of 4"`` -> ``14``).
    """
    lines = text.splitlines()
    for position, line in enumerate(lines):
        if marker.lower() not in line.lower():
            continue
        inline = line.split(":", 1)[-1] if ":" in line else ""
        match = _NUMBER_RE.search(inline)
        if match:
            return float(match.group())
        for candidate in lines[position + 1 : position + 3]:
            stripped = candidate.strip()
            if not stripped:
                continue
            match = _NUMBER_RE.search(stripped)
            if match:
                return float(match.group())
            break
    return default


def _extract_line(text: str, marker: str) -> str | None:
    lines = text.splitlines()
    for position, line in enumerate(lines):
        if line.strip().upper().startswith(marker.upper()):
            remainder = line.split(":", 1)[-1].strip() if ":" in line else ""
            if remainder:
                return remainder
            if position + 1 < len(lines):
                return lines[position + 1].strip()
    return None


def _extract_timeline_topics(text: str) -> list[dict[str, Any]]:
    """Read back the timeline JSON embedded in the rendered Reduce prompt."""
    import json
    import re

    match = re.search(r"CONTENT TIMELINE \(JSON\):\s*(\[.*?\n\]|\{.*?\n\})", text, re.DOTALL)
    if not match:
        return []
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []
    if isinstance(payload, dict):
        return list(payload.get("timeline") or [])
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _format_timestamp(seconds: float) -> str:
    if not math.isfinite(seconds) or seconds < 0:
        seconds = 0
    total = round(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"
