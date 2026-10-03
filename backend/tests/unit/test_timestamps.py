"""Timestamp conversion and formatting tests (spec sections 35, 49, 164, 165)."""

from __future__ import annotations

from app.core.timeutils import format_duration, format_timestamp, parse_timestamp
from app.services.timeline.normalizer import TimelineNormalizer


def test_absolute_conversion_without_offset():
    normalizer = TimelineNormalizer()
    topics = normalizer.normalize(
        [
            {
                "chunk_index": 1,
                "start_seconds": 3540,
                "audio_start_offset": 0.0,
                "duration_seconds": 3600,
                "topics": [
                    {
                        "topic": "Embeddings",
                        "summary": "Explains embeddings.",
                        "start_seconds": 120,
                        "end_seconds": 500,
                    }
                ],
            }
        ]
    )
    assert topics[0]["start_seconds"] == 3660
    assert topics[0]["end_seconds"] == 4040
    assert topics[0]["source_chunk_indices"] == [1]


def test_exact_spec_example_with_audio_stream_offset():
    """audio offset 2 + chunk start 3540 + relative 120 => 3662."""
    normalizer = TimelineNormalizer()
    topics = normalizer.normalize(
        [
            {
                "chunk_index": 1,
                "start_seconds": 3540,
                "audio_start_offset": 2.0,
                "duration_seconds": 3600,
                "topics": [
                    {
                        "topic": "Vectors",
                        "summary": "Vector search overview.",
                        "start_seconds": 120,
                        "end_seconds": 500,
                    }
                ],
            }
        ]
    )
    assert topics[0]["start_seconds"] == 3662
    assert topics[0]["end_seconds"] == 4042


def test_topics_beyond_chunk_duration_are_dropped():
    normalizer = TimelineNormalizer()
    topics = normalizer.normalize(
        [
            {
                "chunk_index": 0,
                "start_seconds": 0,
                "audio_start_offset": 0.0,
                "duration_seconds": 100,
                "topics": [
                    {"topic": "Valid", "summary": "ok", "start_seconds": 1, "end_seconds": 50},
                    {"topic": "Impossible", "summary": "bad", "start_seconds": 40, "end_seconds": 900},
                ],
            }
        ]
    )
    assert [topic["topic"] for topic in topics] == ["Valid"]


def test_end_clamped_to_video_duration():
    normalizer = TimelineNormalizer(video_duration_seconds=3600)
    topics = normalizer.normalize(
        [
            {
                "chunk_index": 1,
                "start_seconds": 3540,
                "audio_start_offset": 0.0,
                "duration_seconds": 3600,
                "topics": [
                    {"topic": "Tail", "summary": "final section", "start_seconds": 0, "end_seconds": 3600}
                ],
            }
        ]
    )
    assert topics[0]["end_seconds"] == 3600


def test_format_timestamp_under_one_hour():
    assert format_timestamp(0) == "00:00"
    assert format_timestamp(462) == "07:42"
    assert format_timestamp(3599) == "59:59"


def test_format_timestamp_over_one_hour():
    assert format_timestamp(3600) == "1:00:00"
    assert format_timestamp(4662) == "1:17:42"
    assert format_timestamp(43473) == "12:04:33"


def test_format_timestamp_never_produces_invalid_values():
    # Rounding must carry into minutes/hours rather than producing "00:60".
    assert format_timestamp(59.6) == "01:00"
    assert format_timestamp(3599.6) == "1:00:00"


def test_parse_timestamp_round_trip():
    assert parse_timestamp("00:00") == 0
    assert parse_timestamp("07:42") == 462
    assert parse_timestamp("1:17:42") == 4662
    assert parse_timestamp("1:99") is None
    assert parse_timestamp("not a timestamp") is None


def test_format_duration_display():
    assert format_duration(0) == "0s"
    assert format_duration(124) == "2m 04s"
    assert format_duration(51484) == "14h 18m 04s"
    assert format_duration(None) == "unknown"
