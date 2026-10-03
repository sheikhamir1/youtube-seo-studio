"""Shared enums.

Python enums are the single source of truth for state names; the database
stores their values so SQLAlchemy/Pydantic representations stay aligned.
"""

from __future__ import annotations

from enum import StrEnum


class JobStatus(StrEnum):
    QUEUED = "QUEUED"
    VALIDATING = "VALIDATING"
    EXTRACTING = "EXTRACTING"
    CHUNKING = "CHUNKING"
    MAPPING = "MAPPING"
    REDUCING = "REDUCING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELED = "CANCELED"


class JobStage(StrEnum):
    """High-level pipeline stage used for progress weighting and log grouping."""

    PENDING = "PENDING"
    VALIDATION = "VALIDATION"
    EXTRACTION = "EXTRACTION"
    CHUNKING = "CHUNKING"
    MAPPING = "MAPPING"
    REDUCTION = "REDUCTION"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"


ACTIVE_JOB_STATUSES: tuple[str, ...] = (
    JobStatus.VALIDATING.value,
    JobStatus.EXTRACTING.value,
    JobStatus.CHUNKING.value,
    JobStatus.MAPPING.value,
    JobStatus.REDUCING.value,
    JobStatus.CANCEL_REQUESTED.value,
)

TERMINAL_JOB_STATUSES: tuple[str, ...] = (
    JobStatus.COMPLETED.value,
    JobStatus.FAILED.value,
    JobStatus.CANCELED.value,
)

# Explicit state machine: only these transitions are accepted.
VALID_JOB_TRANSITIONS: dict[str, set[str]] = {
    JobStatus.QUEUED.value: {
        JobStatus.VALIDATING.value,
        JobStatus.CANCEL_REQUESTED.value,
        JobStatus.CANCELED.value,
        JobStatus.FAILED.value,
    },
    JobStatus.VALIDATING.value: {
        JobStatus.EXTRACTING.value,
        JobStatus.FAILED.value,
        JobStatus.CANCEL_REQUESTED.value,
        JobStatus.CANCELED.value,
        JobStatus.QUEUED.value,  # retry re-queue
    },
    JobStatus.EXTRACTING.value: {
        JobStatus.CHUNKING.value,
        JobStatus.FAILED.value,
        JobStatus.CANCEL_REQUESTED.value,
        JobStatus.CANCELED.value,
        JobStatus.QUEUED.value,
    },
    JobStatus.CHUNKING.value: {
        JobStatus.MAPPING.value,
        JobStatus.FAILED.value,
        JobStatus.CANCEL_REQUESTED.value,
        JobStatus.CANCELED.value,
        JobStatus.QUEUED.value,
    },
    JobStatus.MAPPING.value: {
        JobStatus.REDUCING.value,
        JobStatus.FAILED.value,
        JobStatus.CANCEL_REQUESTED.value,
        JobStatus.CANCELED.value,
        JobStatus.QUEUED.value,
    },
    JobStatus.REDUCING.value: {
        JobStatus.COMPLETED.value,
        JobStatus.FAILED.value,
        JobStatus.CANCEL_REQUESTED.value,
        JobStatus.CANCELED.value,
        JobStatus.QUEUED.value,
    },
    JobStatus.CANCEL_REQUESTED.value: {JobStatus.CANCELED.value},
    JobStatus.COMPLETED.value: set(),  # regeneration creates a new SEO version, not a new run
    JobStatus.FAILED.value: {JobStatus.QUEUED.value, JobStatus.CANCELED.value},
    JobStatus.CANCELED.value: {JobStatus.QUEUED.value},
}


class UploadStatus(StrEnum):
    UPLOADING = "UPLOADING"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"
    FAILED = "FAILED"


class ChunkStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class EventLevel(StrEnum):
    INFO = "INFO"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"


class JobEventType(StrEnum):
    JOB_CREATED = "JOB_CREATED"
    JOB_STARTED = "JOB_STARTED"
    VALIDATION_STARTED = "VALIDATION_STARTED"
    VALIDATION_COMPLETED = "VALIDATION_COMPLETED"
    EXTRACTION_STARTED = "EXTRACTION_STARTED"
    EXTRACTION_PROGRESS = "EXTRACTION_PROGRESS"
    EXTRACTION_COMPLETED = "EXTRACTION_COMPLETED"
    CHUNKING_STARTED = "CHUNKING_STARTED"
    CHUNK_CREATED = "CHUNK_CREATED"
    CHUNKING_COMPLETED = "CHUNKING_COMPLETED"
    MAPPING_STARTED = "MAPPING_STARTED"
    CHUNK_MAPPING_STARTED = "CHUNK_MAPPING_STARTED"
    CHUNK_MAPPING_COMPLETED = "CHUNK_MAPPING_COMPLETED"
    GEMINI_RETRY = "GEMINI_RETRY"
    GEMINI_FILE_CLEANUP_FAILED = "GEMINI_FILE_CLEANUP_FAILED"
    TIMELINE_NORMALIZED = "TIMELINE_NORMALIZED"
    REDUCE_STARTED = "REDUCE_STARTED"
    REDUCE_COMPLETED = "REDUCE_COMPLETED"
    SEO_VALIDATED = "SEO_VALIDATED"
    SEO_VERSION_CREATED = "SEO_VERSION_CREATED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    JOB_CANCELED = "JOB_CANCELED"
    JOB_FAILED = "JOB_FAILED"
    JOB_COMPLETED = "JOB_COMPLETED"
    JOB_RETRY_QUEUED = "JOB_RETRY_QUEUED"
    JOB_RECOVERED = "JOB_RECOVERED"
    WORKER_HEARTBEAT_STALE = "WORKER_HEARTBEAT_STALE"


class SeoGenerationStatus(StrEnum):
    PENDING = "PENDING"
    GENERATING = "GENERATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    VALIDATION_FAILED = "VALIDATION_FAILED"


class AIRequestPhase(StrEnum):
    MAP = "MAP"
    REDUCE = "REDUCE"
    REDUCE_SUMMARY = "REDUCE_SUMMARY"
    REPAIR = "REPAIR"


class AIRequestStatus(StrEnum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    RATE_LIMITED = "RATE_LIMITED"
    TIMEOUT = "TIMEOUT"
    ABORTED = "ABORTED"


class WorkerStatus(StrEnum):
    STARTING = "STARTING"
    IDLE = "IDLE"
    BUSY = "BUSY"
    ERROR = "ERROR"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
