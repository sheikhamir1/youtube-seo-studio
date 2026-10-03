"""Job state machine, retry entry points and progress weights."""

from __future__ import annotations

import pytest

from app.core.constants import STAGE_WEIGHTS
from app.core.errors import ConflictError
from app.services.jobs.progress import compute_progress
from app.services.jobs.state import assert_transition, is_active, is_terminal, retry_entry_point


def test_happy_path_transitions_are_allowed():
    chain = [
        ("QUEUED", "VALIDATING"),
        ("VALIDATING", "EXTRACTING"),
        ("EXTRACTING", "CHUNKING"),
        ("CHUNKING", "MAPPING"),
        ("MAPPING", "REDUCING"),
        ("REDUCING", "COMPLETED"),
    ]
    for current, target in chain:
        assert_transition(current, target)


def test_nonsensical_transitions_are_rejected():
    with pytest.raises(ConflictError):
        assert_transition("COMPLETED", "MAPPING")
    with pytest.raises(ConflictError):
        assert_transition("QUEUED", "COMPLETED")


def test_cancellation_path():
    assert_transition("MAPPING", "CANCEL_REQUESTED")
    assert_transition("CANCEL_REQUESTED", "CANCELED")


def test_retry_requeue_from_failed_and_canceled():
    assert_transition("FAILED", "QUEUED")
    assert_transition("CANCELED", "QUEUED")


def test_status_helpers():
    assert is_active("MAPPING")
    assert is_active("CANCEL_REQUESTED")
    assert is_terminal("COMPLETED")
    assert is_terminal("FAILED")
    assert not is_active("COMPLETED")


@pytest.mark.parametrize(
    ("failed_stage", "has_chunks", "has_timeline", "expected"),
    [
        ("VALIDATION", False, False, "validation"),
        ("EXTRACTION", False, False, "extraction"),
        ("CHUNKING", True, False, "chunking"),
        ("MAPPING", True, False, "map"),
        ("REDUCTION", True, True, "reduce"),
        (None, True, True, "reduce"),
        (None, True, False, "map"),
        (None, False, False, "validation"),
    ],
)
def test_retry_entry_point_never_restarts_from_scratch(failed_stage, has_chunks, has_timeline, expected):
    assert (
        retry_entry_point(failed_stage=failed_stage, has_chunks=has_chunks, has_timeline=has_timeline)
        == expected
    )


def test_stage_weights_sum_to_one_hundred():
    assert sum(STAGE_WEIGHTS.values()) == 100


def test_progress_is_monotonic_across_stages():
    validation = compute_progress(stage="VALIDATION", stage_fraction=1.0)
    extraction = compute_progress(stage="EXTRACTION", stage_fraction=1.0)
    chunking = compute_progress(stage="CHUNKING", stage_fraction=1.0)
    mapping_half = compute_progress(stage="MAPPING", completed_chunks=1, total_chunks=2)
    mapping_done = compute_progress(stage="MAPPING", completed_chunks=2, total_chunks=2)
    reduce_half = compute_progress(stage="REDUCTION", stage_fraction=0.5)
    done = compute_progress(stage="COMPLETED")

    assert validation == 5
    assert extraction == 20
    assert chunking == 35
    assert mapping_half == 60
    assert mapping_done == 85
    assert reduce_half == 92.5
    assert done == 100
    assert validation < extraction < chunking < mapping_half < mapping_done < done


def test_mapping_progress_uses_real_completed_chunks():
    assert compute_progress(stage="MAPPING", completed_chunks=0, total_chunks=13) == 35
    assert compute_progress(stage="MAPPING", completed_chunks=7, total_chunks=13) > 60


def test_failed_and_pending_progress_are_zero():
    assert compute_progress(stage="PENDING") == 0
    assert compute_progress(stage="FAILED") == 0
