"""Map response validation tests (spec sections 44-45, 164)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.ai_map import MapResponse, MapTopic, validate_map_response


def _payload(*topics):
    return {"topics": list(topics)}


def test_valid_payload_parses():
    response, clamps = validate_map_response(
        _payload({"topic": "Embeddings", "summary": "Explained.", "start_seconds": 10, "end_seconds": 40}),
        chunk_duration_seconds=3600,
        max_topics=20,
    )
    assert isinstance(response, MapResponse)
    assert response.topics[0].topic == "Embeddings"
    assert clamps == []


def test_tiny_floating_point_overshoot_is_clamped():
    response, clamps = validate_map_response(
        _payload(
            {
                "topic": "Tail",
                "summary": "Ends at the boundary.",
                "start_seconds": 3599.4,
                "end_seconds": 3600.2,
            }
        ),
        chunk_duration_seconds=3600,
        max_topics=20,
    )
    assert response.topics[0].end_seconds == 3600
    assert clamps and "clamped end" in clamps[0]


def test_large_overshoot_is_rejected_not_repaired():
    with pytest.raises(ValueError):
        validate_map_response(
            _payload(
                {
                    "topic": "Too far",
                    "summary": "Beyond the chunk.",
                    "start_seconds": 100,
                    "end_seconds": 4200,
                }
            ),
            chunk_duration_seconds=3600,
            max_topics=20,
        )


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1.0])
def test_non_finite_and_negative_timestamps_rejected(value):
    with pytest.raises(ValidationError):
        MapTopic(topic="Bad", summary="Bad", start_seconds=value, end_seconds=value + 10)


def test_end_before_start_rejected():
    with pytest.raises(ValidationError):
        MapTopic(topic="Bad", summary="Bad", start_seconds=100, end_seconds=50)


def test_more_topics_than_configured_maximum_is_rejected():
    topics = [
        {
            "topic": f"Topic {index}",
            "summary": "Summary.",
            "start_seconds": index * 10,
            "end_seconds": index * 10 + 5,
        }
        for index in range(25)
    ]
    with pytest.raises(ValueError) as excinfo:
        validate_map_response(_payload(*topics), chunk_duration_seconds=3600, max_topics=20)
    assert "exceeds the configured maximum" in str(excinfo.value)


def test_empty_topic_or_summary_rejected():
    with pytest.raises(ValidationError):
        MapTopic(topic="  ", summary="Summary", start_seconds=0, end_seconds=10)
    with pytest.raises(ValidationError):
        MapTopic(topic="Topic", summary="", start_seconds=0, end_seconds=10)
