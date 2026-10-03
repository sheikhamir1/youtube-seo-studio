"""Prompt template CRUD over the API (validation, uniqueness, snapshots)."""

from __future__ import annotations

import uuid

from app.core.config import settings

prefix = settings.api_v1_prefix


async def test_variables_endpoint_lists_supported_variables(client):
    response = await client.get(f"{prefix}/prompt-templates/variables")
    data = response.json()["data"]
    assert "{{" not in " ".join(data["available_variables"])
    assert "video_title" in data["available_variables"]
    assert "timeline_json" in data["available_variables"]
    assert data["sample_context"]["video_duration_formatted"]


async def test_template_crud_roundtrip(client):
    create = await client.post(
        f"{prefix}/prompt-templates",
        json={
            "name": "Integration Template",
            "description": "Created by the integration suite.",
            "system_prompt": "You are a careful SEO editor.",
            "user_prompt_template": "Title: {{video_title}}\nTimeline: {{timeline_text}}",
        },
    )
    assert create.status_code == 201, create.text
    template = create.json()["data"]
    assert template["variables"] == ["timeline_text", "video_title"]

    # Duplicate names must be rejected.
    duplicate = await client.post(
        f"{prefix}/prompt-templates",
        json={
            "name": "Integration Template",
            "system_prompt": "x",
            "user_prompt_template": "y",
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "PROMPT_TEMPLATE_INVALID"

    # Unknown variables must fail while editing, before any Gemini call happens.
    bad = await client.patch(
        f"{prefix}/prompt-templates/{template['id']}",
        json={"user_prompt_template": "Hello {{not_supported}}"},
    )
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "PROMPT_TEMPLATE_VARIABLE_ERROR"

    # A valid patch works.
    patch = await client.patch(
        f"{prefix}/prompt-templates/{template['id']}",
        json={"name": "Integration Template v2"},
    )
    assert patch.status_code == 200
    assert patch.json()["data"]["name"] == "Integration Template v2"

    # Duplicate helper.
    copy = await client.post(f"{prefix}/prompt-templates/{template['id']}/duplicate")
    assert copy.status_code == 201
    assert copy.json()["data"]["name"].startswith("Integration Template v2 (copy)")

    # Delete.
    delete = await client.delete(f"{prefix}/prompt-templates/{template['id']}")
    assert delete.status_code == 200

    missing = await client.get(f"{prefix}/prompt-templates/{uuid.uuid4()}")
    assert missing.status_code == 404


async def test_default_template_cannot_be_deleted(client, default_template):
    response = await client.delete(f"{prefix}/prompt-templates/{default_template['id']}")
    assert response.status_code == 409
    assert "default template" in response.json()["message"].lower()


async def test_preview_renders_without_calling_gemini(client):
    response = await client.post(
        f"{prefix}/prompt-templates/preview",
        json={"user_prompt_template": "Hello {{video_title}} ({{video_duration_formatted}})"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert "{{" not in data["rendered_user_prompt"]
    assert data["used_variables"] == ["video_duration_formatted", "video_title"]


async def test_seeded_default_template_renders_all_variables(client, default_template):
    """Acceptance test 173: the seeded template renders with no undefined variable."""
    response = await client.post(
        f"{prefix}/prompt-templates/preview",
        json={"user_prompt_template": default_template["user_prompt_template"]},
    )
    rendered = response.json()["data"]["rendered_user_prompt"]
    assert "{{" not in rendered
    assert response.json()["data"]["warnings"] == []
