"""Centralised application error codes and exception types.

The API always answers with the same envelope (see :mod:`app.core.responses`)::

    {"data": null, "message": "...", "error": {"code": "...", "details": "..."}}
"""

from __future__ import annotations

from typing import Any


class ErrorCode:
    """Centralised error codes - never scatter string literals in services."""

    # Uploads
    UPLOAD_SESSION_NOT_FOUND = "UPLOAD_SESSION_NOT_FOUND"
    UPLOAD_PART_INVALID = "UPLOAD_PART_INVALID"
    UPLOAD_INCOMPLETE = "UPLOAD_INCOMPLETE"
    UPLOAD_SIZE_MISMATCH = "UPLOAD_SIZE_MISMATCH"
    UPLOAD_STORAGE_ERROR = "UPLOAD_STORAGE_ERROR"
    UPLOAD_ALREADY_COMPLETED = "UPLOAD_ALREADY_COMPLETED"

    # Media
    MEDIA_NOT_FOUND = "MEDIA_NOT_FOUND"
    MEDIA_INVALID = "MEDIA_INVALID"
    MEDIA_NO_AUDIO = "MEDIA_NO_AUDIO"
    MEDIA_DURATION_UNAVAILABLE = "MEDIA_DURATION_UNAVAILABLE"
    MEDIA_UNREADABLE = "MEDIA_UNREADABLE"

    # FFmpeg
    FFMPEG_NOT_FOUND = "FFMPEG_NOT_FOUND"
    FFMPEG_ERROR = "FFMPEG_ERROR"
    FFPROBE_NOT_FOUND = "FFPROBE_NOT_FOUND"
    FFPROBE_ERROR = "FFPROBE_ERROR"

    # Jobs
    JOB_NOT_FOUND = "JOB_NOT_FOUND"
    INVALID_JOB_STATE = "INVALID_JOB_STATE"
    JOB_CANCELED = "JOB_CANCELED"
    JOB_ALREADY_COMPLETED = "JOB_ALREADY_COMPLETED"
    JOB_QUEUE_UNAVAILABLE = "JOB_QUEUE_UNAVAILABLE"

    # Gemini
    GEMINI_NOT_CONFIGURED = "GEMINI_NOT_CONFIGURED"
    GEMINI_MODEL_UNSUPPORTED = "GEMINI_MODEL_UNSUPPORTED"
    GEMINI_AUDIO_UNSUPPORTED = "GEMINI_AUDIO_UNSUPPORTED"
    GEMINI_AUTH_ERROR = "GEMINI_AUTH_ERROR"
    GEMINI_RATE_LIMIT = "GEMINI_RATE_LIMIT"
    GEMINI_TRANSIENT_ERROR = "GEMINI_TRANSIENT_ERROR"
    GEMINI_SCHEMA_ERROR = "GEMINI_SCHEMA_ERROR"
    GEMINI_SAFETY_BLOCK = "GEMINI_SAFETY_BLOCK"
    GEMINI_FILE_UPLOAD_ERROR = "GEMINI_FILE_UPLOAD_ERROR"
    GEMINI_REQUEST_INVALID = "GEMINI_REQUEST_INVALID"

    # Prompt templates
    PROMPT_TEMPLATE_NOT_FOUND = "PROMPT_TEMPLATE_NOT_FOUND"
    PROMPT_TEMPLATE_INVALID = "PROMPT_TEMPLATE_INVALID"
    PROMPT_TEMPLATE_VARIABLE_ERROR = "PROMPT_TEMPLATE_VARIABLE_ERROR"

    # SEO
    SEO_VALIDATION_ERROR = "SEO_VALIDATION_ERROR"
    SEO_RESULT_NOT_FOUND = "SEO_RESULT_NOT_FOUND"
    CHAPTER_VALIDATION_ERROR = "CHAPTER_VALIDATION_ERROR"

    # Storage / system
    DISK_FULL = "DISK_FULL"
    STORAGE_PERMISSION_ERROR = "STORAGE_PERMISSION_ERROR"
    STORAGE_PATH_ERROR = "STORAGE_PATH_ERROR"
    DATABASE_UNAVAILABLE = "DATABASE_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"


class AppError(Exception):
    """Base class for all handled application errors."""

    code: str = ErrorCode.INTERNAL_ERROR
    http_status: int = 500
    message: str = "Request could not be completed."

    def __init__(
        self,
        message: str | None = None,
        *,
        details: Any = None,
        code: str | None = None,
        http_status: int | None = None,
    ) -> None:
        self.message = message or self.message
        self.details = details
        if code:
            self.code = code
        if http_status:
            self.http_status = http_status
        super().__init__(self.message)


class ValidationError(AppError):
    code = ErrorCode.VALIDATION_ERROR
    http_status = 422
    message = "The submitted data is invalid."


class NotFoundError(AppError):
    code = ErrorCode.NOT_FOUND
    http_status = 404
    message = "Resource not found."


class ConflictError(AppError):
    code = ErrorCode.INVALID_JOB_STATE
    http_status = 409
    message = "The requested operation conflicts with the current state."


class UploadError(AppError):
    code = ErrorCode.UPLOAD_INCOMPLETE
    http_status = 400
    message = "The upload could not be processed."


class MediaError(AppError):
    code = ErrorCode.MEDIA_INVALID
    http_status = 422
    message = "The media file could not be processed."


class FFmpegError(AppError):
    code = ErrorCode.FFMPEG_ERROR
    http_status = 500
    message = "FFmpeg processing failed."


class GeminiError(AppError):
    code = ErrorCode.GEMINI_TRANSIENT_ERROR
    http_status = 502
    message = "The AI provider request failed."


class GeminiRateLimitError(GeminiError):
    code = ErrorCode.GEMINI_RATE_LIMIT
    http_status = 429
    message = "Gemini rate limit reached."


class GeminiAuthError(GeminiError):
    code = ErrorCode.GEMINI_AUTH_ERROR
    http_status = 502
    message = "Gemini authentication failed. Check GEMINI_API_KEY."


class GeminiTransientError(GeminiError):
    code = ErrorCode.GEMINI_TRANSIENT_ERROR
    http_status = 503
    message = "Gemini is temporarily unavailable."


class GeminiSchemaError(GeminiError):
    code = ErrorCode.GEMINI_SCHEMA_ERROR
    http_status = 502
    message = "Gemini returned data that failed schema validation."


class GeminiSafetyBlockError(GeminiError):
    code = ErrorCode.GEMINI_SAFETY_BLOCK
    http_status = 422
    message = "Gemini refused to process this content."


class PromptTemplateError(AppError):
    code = ErrorCode.PROMPT_TEMPLATE_INVALID
    http_status = 422
    message = "The prompt template is invalid."


class SEOValidationError(AppError):
    code = ErrorCode.SEO_VALIDATION_ERROR
    http_status = 422
    message = "The generated SEO output failed validation."


class StorageError(AppError):
    code = ErrorCode.UPLOAD_STORAGE_ERROR
    http_status = 500
    message = "A local storage error occurred."


class DiskFullError(StorageError):
    code = ErrorCode.DISK_FULL
    http_status = 507
    message = (
        "Processing stopped because the local disk became full while writing files. Free up space and retry."
    )


# Errors that are worth retrying against Gemini (transient infrastructure issues).
RETRYABLE_ERROR_CODES: frozenset[str] = frozenset(
    {
        ErrorCode.GEMINI_RATE_LIMIT,
        ErrorCode.GEMINI_TRANSIENT_ERROR,
    }
)

# Errors that must never be retried blindly (permanent configuration problems).
NON_RETRYABLE_ERROR_CODES: frozenset[str] = frozenset(
    {
        ErrorCode.GEMINI_AUTH_ERROR,
        ErrorCode.GEMINI_MODEL_UNSUPPORTED,
        ErrorCode.GEMINI_AUDIO_UNSUPPORTED,
        ErrorCode.GEMINI_SAFETY_BLOCK,
    }
)
