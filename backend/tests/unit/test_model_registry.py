"""Model capability registry: nothing is assumed, everything is declared."""

from __future__ import annotations

import pytest

from app.core.errors import ErrorCode, GeminiError
from app.services.ai import model_registry as registry
from app.services.ai.model_registry import (
    MODEL_PROFILES,
    all_models,
    available_models,
    configured_model_ids,
    default_model,
    get_profile,
    validate_model_for_audio,
)


class TestCapabilities:
    def test_every_known_profile_declares_its_capabilities(self):
        for model_id, profile in MODEL_PROFILES.items():
            assert profile.id == model_id
            assert profile.label
            assert isinstance(profile.supports_audio, bool)
            assert isinstance(profile.supports_structured_output, bool)
            assert profile.capability_known is True

    def test_unknown_model_is_reported_as_unknown(self):
        profile = get_profile("some-unregistered-model")
        assert profile.capability_known is False
        assert profile.supports_audio is False

    def test_default_model_is_configured(self):
        assert default_model() in configured_model_ids()

    def test_available_models_follow_the_configured_order(self):
        available = available_models()
        assert [profile.id for profile in available] == configured_model_ids()


class TestValidation:
    def test_audio_capable_configured_model_is_accepted(self):
        profile = validate_model_for_audio(settings_model())
        assert profile.supports_audio is True

    def test_model_outside_the_allowlist_is_rejected(self, monkeypatch):
        monkeypatch.setattr(registry, "configured_model_ids", lambda: ["gemini-3.5-flash"])
        with pytest.raises(GeminiError) as excinfo:
            validate_model_for_audio("gemini-2.5-flash")
        assert excinfo.value.code == ErrorCode.GEMINI_MODEL_UNSUPPORTED
        assert "GEMINI_ALLOWED_MODELS" in str(excinfo.value)

    def test_audio_incapable_model_is_rejected(self, monkeypatch):
        monkeypatch.setattr(registry, "configured_model_ids", lambda: ["gemini-3.0-text-preview"])
        with pytest.raises(GeminiError) as excinfo:
            validate_model_for_audio("gemini-3.0-text-preview")
        assert excinfo.value.code == ErrorCode.GEMINI_AUDIO_UNSUPPORTED
        assert "audio" in str(excinfo.value).lower()

    def test_unknown_model_capability_is_rejected(self, monkeypatch):
        monkeypatch.setattr(registry, "configured_model_ids", lambda: ["totally-made-up-model"])
        with pytest.raises(GeminiError) as excinfo:
            validate_model_for_audio("totally-made-up-model")
        assert excinfo.value.code == ErrorCode.GEMINI_MODEL_UNSUPPORTED
        assert "capabilit" in str(excinfo.value).lower()


class TestUiPayload:
    def test_all_models_marks_unconfigured_profiles(self):
        entries = {profile.id: is_configured for profile, is_configured in all_models()}
        assert entries["gemini-3.5-flash"] is True
        # Known but not enabled: shown as unavailable rather than hidden.
        assert entries["gemini-3.0-text-preview"] is False
        # Configured models come first so the UI can render them in order.
        ordered = [profile.id for profile, is_configured in all_models() if is_configured]
        assert ordered == configured_model_ids()

    def test_to_dict_exposes_selection_flags(self):
        profile = get_profile("gemini-3.5-flash")
        payload = profile.to_dict(is_default=True, is_configured=True)
        assert payload["is_default"] is True
        assert payload["is_configured"] is True
        assert payload["supports_audio"] is True


def settings_model() -> str:
    return configured_model_ids()[0]
