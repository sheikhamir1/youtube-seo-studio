"""Job lifecycle, validation errors, state conflicts and SSE."""

from __future__ import annotations

import json
import uuid

from app.core.config import settings

prefix = settings.api_v1_prefix


async def test_job_list_is_paginated(client):
    response = await client.get(f"{prefix}/jobs?page=1&page_size=5")
    assert response.status_code == 200
    data = response.json()["data"]
    assert set(data) == {"items", "total", "page", "page_size"}
    assert data["page"] == 1


async def test_create_job_requires_a_completed_upload(client, default_template):
    response = await client.post(
        f"{prefix}/jobs",
        json={
            "upload_id": str(uuid.uuid4()),
            "selected_model": "gemini-3.5-flash",
            "prompt_template_id": str(default_template["id"]),
        },
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "UPLOAD_SESSION_NOT_FOUND"


async def test_model_outside_the_allowlist_is_rejected(client, uploaded_file, default_template):
    """Only models listed in GEMINI_ALLOWED_MODELS may be used.

    ``gemini-3.0-text-preview`` exists in the capability registry (and is
    audio-incapable), but it is not enabled by configuration, so the API must
    refuse it with a message that explains exactly what to change.
    """
    response = await client.post(
        f"{prefix}/jobs",
        json={
            "upload_id": uploaded_file["id"],
            "selected_model": "gemini-3.0-text-preview",
            "prompt_template_id": str(default_template["id"]),
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "GEMINI_MODEL_UNSUPPORTED"
    assert "GEMINI_ALLOWED_MODELS" in response.json()["message"]


async def test_unknown_model_is_rejected_as_unknown_capability(client, uploaded_file, default_template):
    response = await client.post(
        f"{prefix}/jobs",
        json={
            "upload_id": uploaded_file["id"],
            "selected_model": "totally-made-up-model",
            "prompt_template_id": str(default_template["id"]),
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "GEMINI_MODEL_UNSUPPORTED"


async def test_job_creation_is_idempotent_for_the_same_request_id(client, uploaded_file, default_template):
    payload = {
        "upload_id": uploaded_file["id"],
        "selected_model": "gemini-3.5-flash",
        "prompt_template_id": str(default_template["id"]),
        "client_request_id": "double-click-guard",
        "seo_context": {"video_title": "Integration Video", "content_language": "auto"},
    }
    first = await client.post(f"{prefix}/jobs", json=payload)
    assert first.status_code == 201, first.text
    second = await client.post(f"{prefix}/jobs", json=payload)
    assert second.status_code == 200
    assert second.json()["data"]["duplicate"] is True
    assert second.json()["data"]["id"] == first.json()["data"]["id"]

    job_id = first.json()["data"]["id"]

    # The pipeline snapshot must be frozen into the job for reproducibility.
    detail = await client.get(f"{prefix}/jobs/{job_id}")
    job = detail.json()["data"]["job"]
    assert job["pipeline_config"]["chunk_duration_seconds"] == 3600
    assert job["pipeline_config"]["chunk_overlap_seconds"] == 60
    assert job["prompt_template_name_snapshot"] == default_template["name"]

    # Deleting a queued job is allowed only after it is finished/canceled.
    delete = await client.delete(f"{prefix}/jobs/{job_id}")
    assert delete.status_code == 200


async def test_job_state_conflicts_are_reported(client, uploaded_file, default_template):
    create = await client.post(
        f"{prefix}/jobs",
        json={
            "upload_id": uploaded_file["id"],
            "selected_model": "gemini-3.5-flash",
            "prompt_template_id": str(default_template["id"]),
        },
    )
    job_id = create.json()["data"]["id"]

    # A queued job can be canceled, and cancel is idempotent enough to be safe.
    cancel = await client.post(f"{prefix}/jobs/{job_id}/cancel")
    assert cancel.status_code == 200
    assert cancel.json()["data"]["status"] in {"CANCEL_REQUESTED", "CANCELED"}

    # Retry is allowed for canceled jobs and preserves completed work.
    retry = await client.post(f"{prefix}/jobs/{job_id}/retry")
    assert retry.status_code == 200
    assert retry.json()["data"]["status"] == "QUEUED"

    await client.post(f"{prefix}/jobs/{job_id}/cancel")
    await client.delete(f"{prefix}/jobs/{job_id}")


async def test_events_endpoint_and_sse_snapshot(client, uploaded_file, default_template):
    create = await client.post(
        f"{prefix}/jobs",
        json={
            "upload_id": uploaded_file["id"],
            "selected_model": "gemini-3.5-flash",
            "prompt_template_id": str(default_template["id"]),
        },
    )
    job_id = create.json()["data"]["id"]

    events = await client.get(f"{prefix}/jobs/{job_id}/events")
    assert events.status_code == 200
    items = events.json()["data"]["items"]
    assert items and items[0]["event_type"] == "JOB_CREATED"

    # SSE: the first frame must be the current job snapshot.
    async with client.stream("GET", f"{prefix}/jobs/{job_id}/events/stream") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        chunks: list[str] = []
        async for line in response.aiter_lines():
            chunks.append(line)
            if len(chunks) > 6:
                break
    body = "\n".join(chunks)
    assert "event: snapshot" in body
    assert json.dumps(str(job_id)) in body or str(job_id) in body

    await client.post(f"{prefix}/jobs/{job_id}/cancel")
    await client.delete(f"{prefix}/jobs/{job_id}")


async def test_timeline_and_results_are_empty_before_processing(client, uploaded_file, default_template):
    create = await client.post(
        f"{prefix}/jobs",
        json={
            "upload_id": uploaded_file["id"],
            "selected_model": "gemini-3.5-flash",
            "prompt_template_id": str(default_template["id"]),
        },
    )
    job_id = create.json()["data"]["id"]

    timeline = await client.get(f"{prefix}/jobs/{job_id}/timeline")
    assert timeline.json()["data"]["topics"] == []

    current = await client.get(f"{prefix}/jobs/{job_id}/results/current")
    assert current.json()["data"]["result"] is None

    # Regenerating SEO without a timeline must fail with a state conflict.
    regenerate = await client.post(f"{prefix}/jobs/{job_id}/regenerate", json={})
    assert regenerate.status_code == 409
    assert regenerate.json()["error"]["code"] == "INVALID_JOB_STATE"

    await client.post(f"{prefix}/jobs/{job_id}/cancel")
    await client.delete(f"{prefix}/jobs/{job_id}")
