"""The mock Gemini client must produce schema-valid output for every input.

These tests guard the offline/E2E path: if the mock returns something the real
validators reject, every e2e run would silently degrade into endless retries.
"""

from __future__ import annotations

import re
from itertools import pairwise

import pytest

from app.schemas.ai_map import validate_map_response
from app.services.ai.mock_client import MockGeminiClient, _extract_number
from app.services.prompts.defaults import (
    DEFAULT_SEO_USER_PROMPT_TEMPLATE,
    MAP_USER_PROMPT_TEMPLATE,
)
from app.services.prompts.renderer import build_seo_context_values, render_template
from app.services.seo.chapters import parse_timestamp
from app.services.seo.validator import SEOValidator
from tests.fakes import SAMPLE_SEO_CONTEXT, SAMPLE_TIMELINE

CHUNK_DURATIONS = (60.0, 150.0, 1800.0, 3600.0, 7140.0)

_CHAPTER_LINE = re.compile(r"^\s*(?P<ts>\d{1,2}:\d{2}:\d{2}|\d{1,3}:\d{2})\s*(?:[-\u2013\u2014:.)]\s*)?\S")


def _is_chapter(line: str) -> bool:
    return bool(_CHAPTER_LINE.match(line))


def _chapter_seconds(line: str) -> float:
    match = _CHAPTER_LINE.match(line)
    assert match is not None
    seconds = parse_timestamp(match.group("ts"))
    assert seconds is not None
    return seconds


def _map_prompt(duration: float, index: int = 0, start: float = 0.0) -> str:
    return MAP_USER_PROMPT_TEMPLATE.format(
        chunk_index=index,
        chunk_start_seconds=start,
        chunk_duration_seconds=duration,
        max_topics=20,
        content_language="auto",
    )


class TestPromptValueExtraction:
    """Prompt values are rendered on the line *after* their label."""

    def test_reads_next_line_value(self):
        text = "Chunk duration:\n150.0\n\nMaximum topics:\n20\n"
        assert _extract_number(text, "Chunk duration:", default=0.0) == 150.0

    def test_reads_inline_value(self):
        assert _extract_number("Chunk duration: 3600", "Chunk duration:") == 3600.0

    def test_does_not_concatenate_digits(self):
        # "1 of 4" must never become 14.
        assert _extract_number("Chunk index: 1 of 4", "Chunk index:") == 1.0

    def test_returns_default_for_missing_marker(self):
        assert _extract_number("nothing here", "Chunk duration:", default=99.0) == 99.0


class TestMockMapPayload:
    def test_every_chunk_duration_produces_a_valid_payload(self):
        for duration in CHUNK_DURATIONS:
            payload = MockGeminiClient()._map_payload(_map_prompt(duration))
            parsed, clamps = validate_map_response(payload, chunk_duration_seconds=duration, max_topics=20)
            assert parsed.topics, f"no topics for duration {duration}"
            # No clamping should ever be necessary for mock output.
            assert clamps == []
            assert parsed.topics[-1].end_seconds <= duration + 1.5
            for topic in parsed.topics:
                assert topic.end_seconds > topic.start_seconds

    def test_topics_are_chronological(self):
        payload = MockGeminiClient()._map_payload(_map_prompt(3600.0))
        starts = [topic["start_seconds"] for topic in payload["topics"]]
        assert starts == sorted(starts)

    def test_payload_is_rejected_when_it_exceeds_the_topic_limit(self):
        """The mock never exceeds the limit, and the validator enforces it."""
        prompt = _map_prompt(3600.0).replace("Maximum topics:\n20", "Maximum topics:\n3")
        payload = MockGeminiClient()._map_payload(prompt)
        parsed, _ = validate_map_response(payload, chunk_duration_seconds=3600.0, max_topics=20)
        assert len(parsed.topics) == 6
        with pytest.raises(ValueError, match="exceeds the configured maximum"):
            validate_map_response(payload, chunk_duration_seconds=3600.0, max_topics=3)

    def test_chunk_index_changes_the_topics(self):
        first = MockGeminiClient()._map_payload(_map_prompt(1800.0, index=0))
        second = MockGeminiClient()._map_payload(_map_prompt(1800.0, index=1))
        assert first["topics"][0]["topic"] != second["topics"][0]["topic"]


class TestMockReducePayload:
    def _reduce_prompt(self) -> str:
        context = build_seo_context_values(
            seo_context=SAMPLE_SEO_CONTEXT,
            original_filename="advanced-rag-session-4.mp4",
            video_duration_seconds=4320.0,
            timeline=SAMPLE_TIMELINE,
        )
        return render_template(DEFAULT_SEO_USER_PROMPT_TEMPLATE, context)

    def test_reduce_payload_passes_seo_validation(self):
        payload = MockGeminiClient()._seo_payload(self._reduce_prompt())
        output, report = SEOValidator(
            video_duration_seconds=4320.0,
            allowed_chapter_timestamps=[topic["start_seconds"] for topic in SAMPLE_TIMELINE],
            allowed_chapter_windows=[
                (topic["start_seconds"], topic["end_seconds"]) for topic in SAMPLE_TIMELINE
            ],
        ).validate(payload)
        assert output.title
        assert len(output.title) <= 100
        assert len(output.description) <= 5000
        assert output.tags
        assert 0 <= output.seo_score <= 100
        assert report["chapter_validation"]["valid"] is True
        assert report["chapter_validation"]["checks"]["starts_at_zero"] is True
        assert report["chapter_validation"]["count"] >= 3

    def test_reduce_payload_has_three_or_more_spaced_chapters(self):
        payload = MockGeminiClient()._seo_payload(self._reduce_prompt())
        output, _report = SEOValidator(video_duration_seconds=4320.0).validate(payload)
        seconds = [_chapter_seconds(line) for line in output.description.splitlines() if _is_chapter(line)]
        assert len(seconds) >= 3
        assert seconds == sorted(seconds)
        for previous, current in pairwise(seconds):
            assert current - previous >= 10

    def test_reduce_payload_ignores_timestamps_beyond_the_video(self):
        prompt = self._reduce_prompt().replace("4320", "120")
        payload = MockGeminiClient()._seo_payload(prompt)
        output, report = SEOValidator(video_duration_seconds=120.0).validate(payload)
        assert report["chapter_validation"]["valid"] is True
        seconds = [_chapter_seconds(line) for line in output.description.splitlines() if _is_chapter(line)]
        assert seconds and all(seconds <= 120 for seconds in seconds)
