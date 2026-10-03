"""GeminiClient abstraction.

Everything that knows about the Gemini SDK lives here; the rest of the
application only speaks this interface (``RealGeminiClient`` / ``MockGeminiClient``).
"""

from __future__ import annotations

import asyncio
import json
import mimetypes
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from app.core.config import settings
from app.core.errors import ErrorCode, GeminiError
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class UploadedFile:
    name: str
    uri: str
    mime_type: str
    state: str = "ACTIVE"


@dataclass
class UsageMetadata:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    thinking_tokens: int | None = None


@dataclass
class StructuredResponse:
    payload: dict[str, Any]
    usage: UsageMetadata = field(default_factory=UsageMetadata)
    raw_text: str | None = None
    finish_reason: str | None = None


class GeminiClient(Protocol):
    """Interface used by the Map and Reduce services."""

    async def upload_file(self, path: Path, *, mime_type: str | None = None) -> UploadedFile: ...

    async def wait_until_ready(self, file: UploadedFile) -> UploadedFile: ...

    async def generate_structured(
        self,
        *,
        model: str,
        system_instruction: str,
        user_prompt: str,
        schema: dict[str, Any],
        audio_file: UploadedFile | None = None,
        thinking_level: str | None = None,
    ) -> StructuredResponse: ...

    async def delete_file(self, file: UploadedFile) -> None: ...

    @property
    def provider_name(self) -> str: ...


# ---------------------------------------------------------------------------
# Error classification helpers (shared by retry logic)
# ---------------------------------------------------------------------------
def classify_exception(exc: Exception) -> tuple[str, int | None, bool]:
    """Map a provider exception to (error_code, http_status, retryable).

    Retrying is only allowed for transient infrastructure problems - never for
    authentication failures, invalid models, invalid requests or safety blocks.
    """
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    status_code = status if isinstance(status, int) else None
    text = f"{exc.__class__.__name__}: {exc}".lower()

    if status_code == 429 or "rate limit" in text or "quota" in text or "resource_exhausted" in text:
        return ErrorCode.GEMINI_RATE_LIMIT, status_code or 429, True
    if status_code in (500, 502, 503, 504):
        return ErrorCode.GEMINI_TRANSIENT_ERROR, status_code, True
    if "timeout" in text or "deadline" in text:
        return ErrorCode.GEMINI_TRANSIENT_ERROR, status_code, True
    if "connection" in text or "reset" in text or "unavailable" in text:
        return ErrorCode.GEMINI_TRANSIENT_ERROR, status_code, True
    if status_code in (401, 403) or "api key" in text or "unauthenticated" in text or "permission" in text:
        return ErrorCode.GEMINI_AUTH_ERROR, status_code or 401, False
    if status_code == 404 or "not found" in text or "invalid model" in text:
        return ErrorCode.GEMINI_MODEL_UNSUPPORTED, status_code or 404, False
    if "safety" in text or "blocked" in text or "prohibited" in text:
        return ErrorCode.GEMINI_SAFETY_BLOCK, status_code, False
    if status_code == 400 or "invalid argument" in text:
        return ErrorCode.GEMINI_REQUEST_INVALID, status_code or 400, False
    return ErrorCode.GEMINI_TRANSIENT_ERROR, status_code, True


def retry_after_seconds(exc: Exception) -> float | None:
    """Extract a provider Retry-After hint when one is exposed."""
    for attribute in ("retry_after", "retry_delay", "retryDelay"):
        value = getattr(exc, attribute, None)
        if value is None:
            continue
        try:
            if hasattr(value, "total_seconds"):
                return float(value.total_seconds())
            return float(value)
        except (TypeError, ValueError):
            continue
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if headers:
        raw = headers.get("retry-after") or headers.get("Retry-After")
        try:
            return float(raw) if raw is not None else None
        except (TypeError, ValueError):
            return None
    return None


# ---------------------------------------------------------------------------
# Real client (google-genai SDK)
# ---------------------------------------------------------------------------
class RealGeminiClient:
    """Adapter around the official Google Gemini Python SDK.

    The SDK is imported lazily so the application (and its tests) can run
    without the package installed and without an API key.
    """

    def __init__(self, *, api_key: str | None = None) -> None:
        self.api_key = api_key or settings.gemini_api_key
        if not self.api_key:
            raise GeminiError(
                "Gemini API key is not configured. Set GEMINI_API_KEY in your .env file.",
                code=ErrorCode.GEMINI_NOT_CONFIGURED,
                http_status=503,
            )
        self._client = None

    @property
    def provider_name(self) -> str:
        return "gemini"

    def _sdk(self):
        if self._client is not None:
            return self._client
        try:
            from google import genai  # type: ignore
        except ImportError as exc:  # pragma: no cover - dependency missing
            raise GeminiError(
                "The google-genai package is not installed. Run: pip install google-genai",
                code=ErrorCode.GEMINI_NOT_CONFIGURED,
                http_status=503,
            ) from exc
        self._client = genai.Client(api_key=self.api_key)
        return self._client

    async def upload_file(self, path: Path, *, mime_type: str | None = None) -> UploadedFile:
        client = self._sdk()
        guessed = mime_type or mimetypes.guess_type(str(path))[0] or "application/octet-stream"

        def _upload():
            return client.files.upload(file=str(path), config={"mime_type": guessed})

        try:
            result = await asyncio.to_thread(_upload)
        except Exception as exc:
            code, status, _ = classify_exception(exc)
            raise GeminiError(
                "The audio chunk could not be uploaded to the Gemini Files API.",
                details=str(exc)[:500],
                code=ErrorCode.GEMINI_FILE_UPLOAD_ERROR if code else code,
                http_status=status or 502,
            ) from exc

        return UploadedFile(
            name=getattr(result, "name", str(path.name)),
            uri=getattr(result, "uri", ""),
            mime_type=getattr(result, "mime_type", guessed) or guessed,
            state=getattr(getattr(result, "state", None), "name", "ACTIVE") or "ACTIVE",
        )

    async def wait_until_ready(self, file: UploadedFile) -> UploadedFile:
        client = self._sdk()
        deadline = time.monotonic() + settings.gemini_file_ready_timeout_seconds

        def _get():
            return client.files.get(name=file.name)

        while time.monotonic() < deadline:
            result = await asyncio.to_thread(_get)
            state = getattr(getattr(result, "state", None), "name", "ACTIVE") or "ACTIVE"
            file.state = state
            file.uri = getattr(result, "uri", file.uri)
            if state == "ACTIVE":
                return file
            if state == "FAILED":
                raise GeminiError(
                    "Gemini could not process the uploaded audio chunk.",
                    details={"file": file.name, "state": state},
                    code=ErrorCode.GEMINI_FILE_UPLOAD_ERROR,
                )
            await asyncio.sleep(settings.gemini_file_poll_seconds)
        raise GeminiError(
            "Timed out waiting for the Gemini file to become active.",
            details={"file": file.name},
            code=ErrorCode.GEMINI_FILE_UPLOAD_ERROR,
        )

    async def generate_structured(
        self,
        *,
        model: str,
        system_instruction: str,
        user_prompt: str,
        schema: dict[str, Any],
        audio_file: UploadedFile | None = None,
        thinking_level: str | None = None,
    ) -> StructuredResponse:
        client = self._sdk()

        def _generate():
            from google.genai import types  # type: ignore

            contents: list[Any] = []
            if audio_file is not None:
                # Only the extracted audio chunk is ever sent - never the video.
                contents.append(types.Part.from_uri(file_uri=audio_file.uri, mime_type=audio_file.mime_type))
            contents.append(user_prompt)

            config_kwargs: dict[str, Any] = {
                "system_instruction": system_instruction,
                "response_mime_type": "application/json",
                "response_schema": schema,
            }
            if thinking_level:
                try:
                    config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_level=thinking_level)
                except Exception:  # pragma: no cover - SDK variant without thinking config
                    logger.debug("thinking config not supported by installed SDK version")

            config = types.GenerateContentConfig(**config_kwargs)
            return client.models.generate_content(model=model, contents=contents, config=config)

        # Blocking SDK call runs in a worker thread: never block the event loop.
        response = await asyncio.to_thread(_generate)

        payload = self._extract_payload(response)
        usage = self._extract_usage(response)
        finish_reason = None
        candidates = getattr(response, "candidates", None) or []
        if candidates:
            reason = getattr(candidates[0], "finish_reason", None)
            finish_reason = getattr(reason, "name", None) or (str(reason) if reason else None)
        return StructuredResponse(
            payload=payload,
            usage=usage,
            raw_text=getattr(response, "text", None),
            finish_reason=finish_reason,
        )

    async def delete_file(self, file: UploadedFile) -> None:
        client = self._sdk()

        def _delete():
            return client.files.delete(name=file.name)

        await asyncio.to_thread(_delete)

    # -------------------------------------------------------------- internals
    @staticmethod
    def _extract_payload(response: Any) -> dict[str, Any]:
        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, dict):
            return parsed
        if parsed is not None and hasattr(parsed, "model_dump"):
            return parsed.model_dump()
        text = getattr(response, "text", None)
        if not text:
            raise GeminiError(
                "Gemini returned an empty response.",
                code=ErrorCode.GEMINI_SCHEMA_ERROR,
            )
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            cleaned = cleaned.split("\n", 1)[-1] if "\n" in cleaned else cleaned
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise GeminiError(
                "Gemini did not return valid JSON.",
                details=cleaned[:800],
                code=ErrorCode.GEMINI_SCHEMA_ERROR,
            ) from exc

    @staticmethod
    def _extract_usage(response: Any) -> UsageMetadata:
        usage = getattr(response, "usage_metadata", None)
        if usage is None:
            return UsageMetadata()
        return UsageMetadata(
            input_tokens=getattr(usage, "prompt_token_count", None),
            output_tokens=getattr(usage, "candidates_token_count", None),
            total_tokens=getattr(usage, "total_token_count", None),
            thinking_tokens=getattr(usage, "thoughts_token_count", None),
        )


def build_client(provider: str | None = None) -> GeminiClient:
    """Factory: real Gemini client or the deterministic mock client."""
    resolved = (provider or settings.ai_provider).lower()
    if resolved == "mock":
        from app.services.ai.mock_client import MockGeminiClient

        logger.warning("AI_PROVIDER=mock: deterministic mock AI responses are in use")
        return MockGeminiClient()
    return RealGeminiClient()
