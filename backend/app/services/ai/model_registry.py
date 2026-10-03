"""Model capability registry.

Capabilities are declared explicitly. Unknown models are reported as unknown and
must be configured before use - the application never silently assumes support.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from app.core.config import settings


@dataclass(frozen=True)
class ModelProfile:
    id: str
    label: str
    supports_audio: bool
    supports_structured_output: bool
    capability_known: bool = True
    thinking_level_default: str | None = None
    notes: str | None = None

    def to_dict(self, *, is_default: bool = False, is_configured: bool = True) -> dict:
        payload = asdict(self)
        payload["is_default"] = is_default
        # ``is_configured`` = the model is enabled in GEMINI_ALLOWED_MODELS and
        # may therefore be selected for a new analysis.
        payload["is_configured"] = is_configured
        return payload


MODEL_PROFILES: dict[str, ModelProfile] = {
    "gemini-3.5-flash-lite": ModelProfile(
        id="gemini-3.5-flash-lite",
        label="Gemini 3.5 Flash lite",
        supports_audio=True,
        supports_structured_output=True,
        thinking_level_default="high",
        notes="Default model: audio understanding with long-context support.",
    ),
    "gemini-3.1-flash-lite": ModelProfile(
        id="gemini-3.1-flash-lite",
        label="Gemini 3.1 Flash lite",
        supports_audio=True,
        supports_structured_output=True,
        thinking_level_default="high",
        notes="2nd Model: audio understanding with long-context support.",
    ),
    "gemini-3.8-flash": ModelProfile(
        id="gemini-3.8-flash",
        label="Gemini 3.8 Flash",
        supports_audio=True,
        supports_structured_output=True,
        thinking_level_default="low",
        notes="New Model But Limited RPD",
    ),
    # A deliberately declared-but-incapable profile so the UI can prove that
    # audio-incapable models are disabled rather than silently switched.
    "gemini-3.0-text-preview": ModelProfile(
        id="gemini-3.0-text-preview",
        label="Gemini 3.0 Text Preview",
        supports_audio=False,
        supports_structured_output=True,
        thinking_level_default=None,
        notes="Text-only preview model: audio analysis is not supported.",
    ),
}


def get_profile(model_id: str) -> ModelProfile:
    """Return a profile for a configured model id."""
    profile = MODEL_PROFILES.get(model_id)
    if profile is not None:
        return profile
    # Unknown model from environment configuration: capability metadata is
    # explicitly unknown, so the UI requires confirmation before use.
    return ModelProfile(
        id=model_id,
        label=model_id,
        supports_audio=False,
        supports_structured_output=False,
        capability_known=False,
        notes="Unknown model: capability metadata must be configured before use.",
    )


def available_models() -> list[ModelProfile]:
    """Models allowed by configuration, ordered with the default first."""
    configured = settings.allowed_models or [settings.gemini_model]
    ordered: list[ModelProfile] = []
    for model_id in configured:
        profile = MODEL_PROFILES.get(model_id)
        ordered.append(
            profile
            if profile is not None
            else ModelProfile(
                id=model_id,
                label=model_id,
                supports_audio=False,
                supports_structured_output=False,
                capability_known=False,
                notes="Unknown model: capability metadata must be configured before use.",
            )
        )
    return ordered


def configured_model_ids() -> list[str]:
    return list(settings.allowed_models or [settings.gemini_model])


def all_models() -> list[tuple[ModelProfile, bool]]:
    """Every model the UI may show, paired with its selectable flag.

    Configured models come first (in configured order); known profiles that are
    not enabled follow so the interface can display them as unavailable instead
    of hiding them, which would look like the capability check is missing.
    """
    configured = configured_model_ids()
    ordered: list[tuple[ModelProfile, bool]] = [(profile, True) for profile in available_models()]
    for model_id, profile in MODEL_PROFILES.items():
        if model_id not in configured:
            ordered.append((profile, False))
    return ordered


def validate_model_for_audio(model_id: str) -> ModelProfile:
    """Raise a clear error when a model cannot process audio."""
    from app.core.errors import ErrorCode, GeminiError

    if model_id not in configured_model_ids():
        raise GeminiError(
            f"Model '{model_id}' is not enabled. Add it to GEMINI_ALLOWED_MODELS in .env to use it.",
            code=ErrorCode.GEMINI_MODEL_UNSUPPORTED,
            http_status=422,
        )

    profile = get_profile(model_id)
    if not profile.capability_known:
        raise GeminiError(
            f"Model '{model_id}' has unknown capabilities. Configure capability metadata before use.",
            code=ErrorCode.GEMINI_MODEL_UNSUPPORTED,
            http_status=422,
        )
    if not profile.supports_audio:
        raise GeminiError(
            "Audio input not supported by the selected model.",
            code=ErrorCode.GEMINI_AUDIO_UNSUPPORTED,
            http_status=422,
        )
    return profile


def default_model() -> str:
    return settings.gemini_model
