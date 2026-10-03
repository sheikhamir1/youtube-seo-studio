"""SEO output validation tests: title/description/tags/score/chapters."""

from __future__ import annotations

import pytest

from app.core.constants import DESCRIPTION_MAX_CHARS, TITLE_MAX_CHARS
from app.core.errors import SEOValidationError
from app.services.seo.chapters import (
    extract_chapters,
    repair_description_chapters,
    validate_chapters,
)
from app.services.seo.validator import SEOValidator

TIMELINE = [
    {"topic": "Introduction", "summary": "Frames the session.", "start_seconds": 0, "end_seconds": 600},
    {"topic": "Core concepts", "summary": "Explains the theory.", "start_seconds": 600, "end_seconds": 2400},
    {
        "topic": "Worked example",
        "summary": "Practical walkthrough.",
        "start_seconds": 2400,
        "end_seconds": 3600,
    },
]


def _payload(**overrides):
    base = {
        "title": "Advanced RAG Course: Embeddings and Vector Search Explained",
        "description": (
            "A full session on retrieval-augmented generation, embeddings and vector search.\n\n"
            "Chapters:\n00:00 Introduction\n05:00 Core concepts\n20:00 Worked example\n\n"
            "Recorded locally and analysed with YouTube SEO Studio."
        ),
        "tags": ["RAG", "embeddings", "vector search", "machine learning"],
        "seo_score": 87,
        "improvement_suggestions": "Add one more supporting keyword to the opening line.",
        "thumbnail_prompt": (
            "16:9 YouTube thumbnail with a dark slate background and an indigo accent, a presenter "
            "at a desk with two screen overlays showing vectors, bold readable title area on the left."
        ),
    }
    base.update(overrides)
    return base


def test_valid_payload_passes_and_reports_metadata():
    validator = SEOValidator(
        video_duration_seconds=4320,
        allowed_chapter_timestamps=[topic["start_seconds"] for topic in TIMELINE],
        # Real topic windows: a chapter inside a topic's range is grounded.
        allowed_chapter_windows=[(topic["start_seconds"], topic["end_seconds"]) for topic in TIMELINE],
    )
    output, metadata = validator.validate(_payload())
    assert output.seo_score == 87
    assert metadata["title_length"] <= TITLE_MAX_CHARS
    assert metadata["chapter_validation"]["valid"] is True
    assert metadata["chapter_validation"]["count"] == 3
    assert metadata["errors"] == []


def test_title_over_limit_is_rejected():
    validator = SEOValidator(video_duration_seconds=4320)
    with pytest.raises(SEOValidationError) as excinfo:
        validator.validate(_payload(title="A" * 120))
    assert "100" in str(excinfo.value)


def test_description_over_limit_is_rejected():
    validator = SEOValidator(video_duration_seconds=4320)
    long_description = _payload()["description"] + (" extra text" * 600)
    with pytest.raises(SEOValidationError):
        validator.validate(_payload(description=long_description))
    assert len(long_description) > DESCRIPTION_MAX_CHARS


def test_duplicate_tags_are_deduplicated_case_insensitively():
    validator = SEOValidator(video_duration_seconds=4320)
    output, metadata = validator.validate(_payload(tags=["RAG", "rag", " RAG ", "embeddings", ""]))
    assert output.tags == ["RAG", "embeddings"]
    assert metadata["tag_count"] == 2


def test_empty_tags_rejected():
    validator = SEOValidator(video_duration_seconds=4320)
    with pytest.raises(SEOValidationError):
        validator.validate(_payload(tags=["", "  "]))


def test_score_out_of_range_rejected():
    validator = SEOValidator(video_duration_seconds=4320)
    with pytest.raises(SEOValidationError):
        validator.validate(_payload(seo_score=140))


def test_missing_chapters_rejected_for_long_form():
    validator = SEOValidator(video_duration_seconds=4320)
    with pytest.raises(SEOValidationError) as excinfo:
        validator.validate(_payload(description="No chapters at all in this description."))
    assert "at least 3 chapters" in str(excinfo.value).lower() or "chapter" in str(excinfo.value).lower()


def test_chapters_must_start_at_zero():
    validator = SEOValidator(video_duration_seconds=4320)
    description = "Chapters:\n00:10 Introduction\n05:00 Core\n20:00 Example"
    with pytest.raises(SEOValidationError):
        validator.validate(_payload(description=description))


def test_chapters_must_be_ascending():
    report = validate_chapters(
        "Chapters:\n02:00 Second\n01:00 First\n30:00 Third", video_duration_seconds=3600
    )
    assert report["valid"] is False
    assert report["checks"]["chronological"] is False


def test_short_timestamp_typo_is_repaired_deterministically():
    text, repairs = repair_description_chapters("Chapters:\n00:0 Intro\n05:00 Core\n20:00 Example")
    assert repairs, "a repair should be recorded"
    chapters = extract_chapters(text)
    assert chapters[0]["seconds"] == 0
    assert chapters[0]["timestamp"] == "00:00"


def test_duplicate_chapter_timestamps_removed():
    text, repairs = repair_description_chapters(
        "Chapters:\n00:00 Intro\n05:00 Core\n05:00 Core again\n20:00 Example"
    )
    assert any("duplicate" in repair for repair in repairs)
    assert len(extract_chapters(text)) == 3


def test_chapter_out_of_order_is_sorted_when_semantics_allow():
    text, repairs = repair_description_chapters("00:00 Intro\n20:00 Example\n05:00 Core")
    assert any("sorted" in repair for repair in repairs)
    seconds = [chapter["seconds"] for chapter in extract_chapters(text)]
    assert seconds == sorted(seconds)


def test_chapter_spacing_is_enforced():
    report = validate_chapters("00:00 Intro\n00:05 Too close\n00:10 Still close", video_duration_seconds=3600)
    assert report["checks"]["spacing_valid"] is False


def test_chapters_beyond_video_duration_rejected():
    report = validate_chapters("00:00 Intro\n05:00 Core\n90:00 Beyond", video_duration_seconds=3600)
    # "90:00" is not a valid timestamp at all: it must fail loudly, not vanish.
    assert report["valid"] is False
    assert report["checks"]["timestamps_parseable"] is False
    assert any("Impossible" in issue for issue in report["issues"])


def test_valid_timestamp_beyond_duration_rejected():
    report = validate_chapters("00:00 Intro\n05:00 Core\n1:30:00 Beyond", video_duration_seconds=3600)
    assert report["valid"] is False
    assert report["checks"]["within_duration"] is False


def test_live_chapter_validation_accepts_in_window_timestamps():
    report = validate_chapters(
        _payload()["description"],
        video_duration_seconds=4320,
        allowed_windows=[(topic["start_seconds"], topic["end_seconds"]) for topic in TIMELINE],
    )
    assert report["valid"] is True
    assert report["checks"]["timestamps_grounded"] is True


def test_chapters_must_map_to_the_supplied_timeline():
    validator = SEOValidator(
        video_duration_seconds=4320,
        allowed_chapter_timestamps=[0.0, 4000.0],
    )
    description = "Chapters:\n00:00 Intro\n05:00 Core concepts\n20:00 Worked example"
    with pytest.raises(SEOValidationError):
        validator.validate(_payload(description=description))
