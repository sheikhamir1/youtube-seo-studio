"""Health, readiness and system endpoints."""

from __future__ import annotations

from app.core.config import settings

pytest_plugins: list[str] = []
prefix = settings.api_v1_prefix


async def test_health_ok(client):
    response = await client.get(f"{prefix}/health")
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["status"] == "ok"
    assert body["error"] is None


async def test_ready_reports_dependencies(client):
    response = await client.get(f"{prefix}/ready")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["database"]["ok"] is True, data["database"]
    assert "gemini_key_configured" in data


async def test_system_status_never_leaks_the_api_key(client):
    response = await client.get(f"{prefix}/system/status")
    assert response.status_code == 200
    data = response.json()["data"]
    assert "gemini_key_configured" in data
    assert "gemini_api_key" not in str(data).lower()
    assert data["data_dir"]


async def test_models_endpoint_reports_capabilities(client):
    response = await client.get(f"{prefix}/system/models")
    data = response.json()["data"]
    assert data["default_model"] == "gemini-3.5-flash"
    profiles = {model["id"]: model for model in data["models"]}
    assert profiles["gemini-3.5-flash"]["supports_audio"] is True
    assert profiles["gemini-3.5-flash"]["is_configured"] is True
    # Capability metadata is never assumed: a text-only model is reported as
    # audio-incapable AND not selectable.
    text_model = profiles["gemini-3.0-text-preview"]
    assert text_model["supports_audio"] is False
    assert text_model["is_configured"] is False
    assert "gemini-3.0-text-preview" not in data["selectable_models"]
    assert "gemini-3.5-flash" in data["selectable_models"]


async def test_quota_endpoint_is_labelled_as_application_tracked(client):
    response = await client.get(f"{prefix}/system/quota")
    data = response.json()["data"]
    assert data["label"] == "Application-tracked usage"
    assert data["rpd_limit"] >= 1
