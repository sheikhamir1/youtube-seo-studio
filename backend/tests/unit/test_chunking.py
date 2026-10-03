"""Chunk math tests - the exact examples from the specification."""

from __future__ import annotations

from itertools import pairwise

import pytest

from app.services.media.chunking import (
    ChunkBoundary,
    compute_step,
    count_chunks,
    estimate_audio_tokens,
    plan_chunks,
    refine_chunks_for_token_budget,
)


def test_step_is_duration_minus_overlap():
    # Adjacent chunks overlap by 60 s, so the next chunk starts 3540 s later.
    assert compute_step(3600, 60) == 3540


def test_single_chunk_video():
    boundaries = plan_chunks(3600, chunk_duration_seconds=3600, chunk_overlap_seconds=60)
    assert len(boundaries) == 1
    assert boundaries[0].start_seconds == 0
    assert boundaries[0].end_seconds == 3600


def test_short_video_smaller_than_chunk():
    boundaries = plan_chunks(180, chunk_duration_seconds=3600, chunk_overlap_seconds=60)
    assert len(boundaries) == 1
    assert boundaries[0].duration_seconds == 180


def test_two_hour_video_boundaries():
    boundaries = plan_chunks(7140, chunk_duration_seconds=3600, chunk_overlap_seconds=60)
    assert [(b.start_seconds, b.end_seconds) for b in boundaries] == [(0, 3600), (3540, 7140)]


def test_twelve_hour_video_is_dynamic_not_hardcoded():
    twelve_hours = 12 * 3600
    boundaries = plan_chunks(twelve_hours, chunk_duration_seconds=3600, chunk_overlap_seconds=60)
    # 43200 s / 3540 s step => 13 chunks (12 * 3540 = 42480 < 43200).
    assert len(boundaries) == count_chunks(twelve_hours, chunk_duration=3600, overlap=60)
    assert boundaries[-1].end_seconds == twelve_hours
    for previous, current in pairwise(boundaries):
        # Every adjacent pair overlaps by exactly 60 seconds.
        assert round(previous.end_seconds - current.start_seconds, 3) == 60
        assert current.start_seconds < previous.end_seconds


def test_fourteen_hour_video_is_not_rejected():
    fourteen_hours = 14 * 3600
    boundaries = plan_chunks(fourteen_hours, chunk_duration_seconds=3600, chunk_overlap_seconds=60)
    assert len(boundaries) == 15
    assert boundaries[-1].end_seconds == fourteen_hours


def test_final_partial_chunk_is_shorter():
    boundaries = plan_chunks(7200, chunk_duration_seconds=3600, chunk_overlap_seconds=60)
    assert len(boundaries) == 3
    assert boundaries[-1].duration_seconds == 7200 - 7080
    assert boundaries[-1].end_seconds == 7200


def test_chunks_are_never_larger_than_nominal_duration():
    boundaries = plan_chunks(36000, chunk_duration_seconds=3600, chunk_overlap_seconds=60)
    assert all(b.duration_seconds <= 3600 for b in boundaries)


def test_zero_or_negative_duration_returns_no_chunks():
    assert plan_chunks(0) == []
    assert plan_chunks(-10) == []


def test_overlap_larger_than_half_duration_is_clamped():
    # Pathological configuration must not produce an infinite loop.
    assert compute_step(60, 120) == 30


def test_audio_token_estimation_default_rate():
    # 3600 s * 32 tokens/s = 115,200 tokens.
    assert estimate_audio_tokens(3600) == 115_200


def test_adaptive_split_when_token_budget_is_exceeded():
    boundaries = plan_chunks(7200, chunk_duration_seconds=3600, chunk_overlap_seconds=60)
    refined = refine_chunks_for_token_budget(
        boundaries,
        chunk_overlap_seconds=60,
        max_safe_input_tokens=60_000,  # forces ~30 minute chunks
        tokens_per_second=32,
    )
    assert len(refined) > len(boundaries)
    assert all(b.duration_seconds <= 3600 for b in refined)
    # The refined plan still covers the whole audio.
    assert refined[-1].end_seconds == pytest.approx(7200, abs=1)
    assert [b.chunk_index for b in refined] == list(range(len(refined)))


def test_no_split_when_budget_is_generous():
    boundaries = plan_chunks(7200, chunk_duration_seconds=3600, chunk_overlap_seconds=60)
    refined = refine_chunks_for_token_budget(
        boundaries,
        chunk_overlap_seconds=60,
        max_safe_input_tokens=180_000,
        tokens_per_second=32,
    )
    assert refined == boundaries


def test_boundary_serialisation():
    boundary = ChunkBoundary(chunk_index=1, start_seconds=3540, end_seconds=7140, duration_seconds=3600)
    payload = boundary.to_dict()
    assert payload == {
        "chunk_index": 1,
        "start_seconds": 3540,
        "end_seconds": 7140,
        "duration_seconds": 3600,
    }
