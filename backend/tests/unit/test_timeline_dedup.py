"""Overlap deduplication tests (spec sections 51-53, acceptance test 269)."""

from __future__ import annotations

from app.services.timeline.dedup import (
    merge_topics,
    normalize_topic_string,
    topics_are_duplicates,
)
from app.services.timeline.normalizer import TimelineNormalizer

THRESHOLD = 0.88
PROXIMITY = 90.0


def _topic(topic: str, summary: str, start: float, end: float, chunks: list[int] | None = None):
    return {
        "topic": topic,
        "summary": summary,
        "start_seconds": start,
        "end_seconds": end,
        "source_chunk_indices": chunks or [0],
    }


def test_overlap_duplicate_is_merged():
    """The same topic at the end of chunk 0 and the start of chunk 1."""
    left = _topic("Introduction to embeddings", "Explains what embeddings are.", 3550, 3600, [0])
    right = _topic("Introduction to embeddings", "Explains what embeddings are in detail.", 3600, 3660, [1])
    duplicate, score = topics_are_duplicates(left, right, threshold=THRESHOLD, proximity_seconds=PROXIMITY)
    assert duplicate is True
    assert score >= THRESHOLD

    merged = merge_topics(left, right)
    assert merged["start_seconds"] == 3550
    assert merged["end_seconds"] == 3660
    assert merged["source_chunk_indices"] == [0, 1]
    # The more informative summary wins.
    assert "in detail" in merged["summary"]


def test_distinct_neighbours_are_not_merged():
    left = _topic("Embeddings", "Explains vector embeddings.", 100, 400, [0])
    right = _topic("Vector database indexing", "Covers HNSW indexing trade-offs.", 410, 900, [1])
    duplicate, score = topics_are_duplicates(left, right, threshold=THRESHOLD, proximity_seconds=PROXIMITY)
    assert duplicate is False
    assert score < THRESHOLD


def test_similar_titles_far_apart_in_time_are_not_merged():
    """Text similarity alone must never merge two distant sections."""
    left = _topic("Summary and next steps", "Wrap-up of the first half.", 100, 200, [0])
    right = _topic("Summary and next steps", "Wrap-up of the second half.", 9000, 9100, [5])
    duplicate, _ = topics_are_duplicates(left, right, threshold=THRESHOLD, proximity_seconds=PROXIMITY)
    assert duplicate is False


def test_normalizer_merges_end_to_end_and_sorts():
    normalizer = TimelineNormalizer(
        similarity_threshold=THRESHOLD, proximity_seconds=PROXIMITY, video_duration_seconds=7200
    )
    topics = normalizer.normalize(
        [
            {
                "chunk_index": 0,
                "start_seconds": 0,
                "audio_start_offset": 0.0,
                "duration_seconds": 3600,
                "topics": [
                    {
                        "topic": "Welcome and agenda",
                        "summary": "Intro.",
                        "start_seconds": 0,
                        "end_seconds": 300,
                    },
                    {
                        "topic": "Introduction to embeddings",
                        "summary": "Explains embeddings.",
                        "start_seconds": 3400,
                        "end_seconds": 3600,
                    },
                ],
            },
            {
                "chunk_index": 1,
                "start_seconds": 3540,
                "audio_start_offset": 0.0,
                "duration_seconds": 3660,
                "topics": [
                    # relative 60 s inside chunk 1 == absolute 3600 s: same topic.
                    {
                        "topic": "Introduction to embeddings",
                        "summary": "Explains embeddings and their dimensions in detail.",
                        "start_seconds": 60,
                        "end_seconds": 900,
                    },
                    {
                        "topic": "Vector search",
                        "summary": "How similarity search works.",
                        "start_seconds": 900,
                        "end_seconds": 1800,
                    },
                ],
            },
        ]
    )
    labels = [topic["topic"] for topic in topics]
    assert labels.count("Introduction to embeddings") == 1
    assert labels == ["Welcome and agenda", "Introduction to embeddings", "Vector search"]
    merged = topics[1]
    assert merged["start_seconds"] == 3400
    assert merged["end_seconds"] == 4440
    assert merged["source_chunk_indices"] == [0, 1]
    # Chronological ordering is deterministic.
    starts = [topic["start_seconds"] for topic in topics]
    assert starts == sorted(starts)


def test_normalize_topic_string_removes_filler():
    assert normalize_topic_string("Introduction to the Core Concept!") == "core concept"
    assert normalize_topic_string("Types of Embeddings") == "types embeddings"
