"""Resumable upload behaviour over the real API."""

from __future__ import annotations

from app.core.config import settings

prefix = settings.api_v1_prefix


# 64 KiB is the documented minimum part size (see UploadCreateRequest).
PART_SIZE = 64 * 1024


async def test_upload_session_lifecycle_and_resume(client):
    content = b"abcdefghij" * 16384  # 160 KiB => 64 KiB + 64 KiB + 32 KiB parts
    part_size = PART_SIZE

    create = await client.post(
        f"{prefix}/uploads",
        json={
            "filename": "my lecture.mp4",
            "content_type": "video/mp4",
            "size_bytes": len(content),
            "chunk_size_bytes": part_size,
        },
    )
    assert create.status_code == 201, create.text
    session = create.json()["data"]
    assert session["total_parts"] == 3
    upload_id = session["id"]

    # Upload only the first two parts, then simulate a browser refresh.
    for part_number in (0, 1):
        response = await client.put(
            f"{prefix}/uploads/{upload_id}/parts/{part_number}",
            content=content[part_number * part_size : (part_number + 1) * part_size],
        )
        assert response.status_code == 200

    status = await client.get(f"{prefix}/uploads/{upload_id}")
    data = status.json()["data"]
    assert data["received_size"] == 2 * part_size
    assert data["received_parts"] == [0, 1]
    assert data["next_missing_part"] == 2
    assert data["progress_percent"] == 80.0

    # Completing too early must fail with a clear, specific error.
    premature = await client.post(f"{prefix}/uploads/{upload_id}/complete")
    assert premature.status_code == 409
    assert premature.json()["error"]["code"] == "UPLOAD_INCOMPLETE"

    # Resume: upload the remaining part and complete.
    last = await client.put(f"{prefix}/uploads/{upload_id}/parts/2", content=content[2 * part_size :])
    assert last.status_code == 200

    complete = await client.post(f"{prefix}/uploads/{upload_id}/complete")
    assert complete.status_code == 200
    assert complete.json()["data"]["status"] == "COMPLETED"

    # Re-completing an already finished session is idempotent.
    again = await client.post(f"{prefix}/uploads/{upload_id}/complete")
    assert again.status_code == 200


async def test_out_of_range_part_number_is_rejected(client):
    create = await client.post(
        f"{prefix}/uploads",
        json={
            "filename": "clip.mp4",
            "content_type": "video/mp4",
            "size_bytes": 2 * PART_SIZE,
            "chunk_size_bytes": PART_SIZE,
        },
    )
    assert create.status_code == 201, create.text
    upload_id = create.json()["data"]["id"]
    response = await client.put(f"{prefix}/uploads/{upload_id}/parts/5", content=b"x" * 10)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UPLOAD_PART_INVALID"


async def test_unknown_upload_session_returns_not_found(client):
    response = await client.get(f"{prefix}/uploads/11111111-1111-1111-1111-111111111111")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "UPLOAD_SESSION_NOT_FOUND"


async def test_part_size_config_is_informational(client):
    response = await client.get(f"{prefix}/uploads/config/part-size")
    data = response.json()["data"]
    assert data["chunk_size_bytes"] == settings.upload_part_size_mb * 1024 * 1024
    assert "not a total file-size limit" in data["note"]
