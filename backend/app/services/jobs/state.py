"""Job state machine: explicit, validated transitions."""

from __future__ import annotations

from app.core.enums import (
    ACTIVE_JOB_STATUSES,
    TERMINAL_JOB_STATUSES,
    VALID_JOB_TRANSITIONS,
    JobStage,
    JobStatus,
)
from app.core.errors import ConflictError, ErrorCode


def assert_transition(current: str, target: str) -> None:
    """Raise a 409 when a transition is not part of the state machine."""
    if current == target:
        return
    allowed = VALID_JOB_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise ConflictError(
            f"Cannot move job from {current} to {target}.",
            details={"current_status": current, "requested_status": target},
            code=ErrorCode.INVALID_JOB_STATE,
        )


def is_active(status: str) -> bool:
    return status in ACTIVE_JOB_STATUSES


def is_terminal(status: str) -> bool:
    return status in TERMINAL_JOB_STATUSES


def stage_for_status(status: str) -> str:
    return {
        JobStatus.QUEUED.value: JobStage.PENDING.value,
        JobStatus.VALIDATING.value: JobStage.VALIDATION.value,
        JobStatus.EXTRACTING.value: JobStage.EXTRACTION.value,
        JobStatus.CHUNKING.value: JobStage.CHUNKING.value,
        JobStatus.MAPPING.value: JobStage.MAPPING.value,
        JobStatus.REDUCING.value: JobStage.REDUCTION.value,
        JobStatus.COMPLETED.value: JobStage.COMPLETED.value,
        JobStatus.FAILED.value: JobStage.FAILED.value,
        JobStatus.CANCELED.value: JobStage.CANCELED.value,
        JobStatus.CANCEL_REQUESTED.value: JobStage.PENDING.value,
    }.get(status, JobStage.PENDING.value)


def retry_entry_point(*, failed_stage: str | None, has_chunks: bool, has_timeline: bool) -> str:
    """Decide where a retry resumes - never restart the whole pipeline blindly.

    validation failure -> re-validate
    extraction failure -> re-extract
    chunking failure   -> reuse valid chunks
    map failure        -> reuse completed chunks
    reduce failure     -> reuse the timeline
    """
    stage = (failed_stage or "").upper()
    if stage in {JobStage.REDUCTION.value, "REDUCING", "REDUCE"} and has_timeline:
        return "reduce"
    if stage in {JobStage.MAPPING.value, "MAPPING"} and has_chunks:
        return "map"
    if stage in {JobStage.CHUNKING.value, "CHUNKING"} and has_chunks:
        return "chunking"
    if stage in {JobStage.EXTRACTION.value, "EXTRACTING"}:
        return "extraction"
    if stage in {JobStage.VALIDATION.value, "VALIDATING"}:
        return "validation"
    if has_timeline:
        return "reduce"
    if has_chunks:
        return "map"
    return "validation"
