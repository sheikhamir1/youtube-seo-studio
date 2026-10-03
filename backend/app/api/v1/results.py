"""SEO result endpoints: versions, manual editing, restore, validation."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ErrorCode, NotFoundError, SEOValidationError
from app.core.responses import success
from app.db.dependencies import get_db
from app.repositories.jobs import JobRepository
from app.repositories.results import SEOResultRepository
from app.schemas.seo import SEOResultUpdate
from app.services.seo.chapters import extract_chapters, validate_chapters
from app.services.seo.validator import SEOValidator

router = APIRouter(prefix="/jobs", tags=["results"])


def _serialize(result) -> dict:
    return {
        "id": result.id,
        "job_id": result.job_id,
        "version_number": result.version_number,
        "title": result.title,
        "description": result.description,
        "tags": result.tags,
        "seo_score": result.seo_score,
        "improvement_suggestions": result.improvement_suggestions,
        "thumbnail_prompt": result.thumbnail_prompt,
        "model": result.model,
        "prompt_template_id": result.prompt_template_id,
        "prompt_template_name_snapshot": result.prompt_template_name_snapshot,
        "validation_metadata": result.validation_metadata,
        "chapters": result.chapters or _chapter_payload(result.description),
        "is_current": result.is_current,
        "edited_by_user": result.edited_by_user,
        "created_at": result.created_at,
        "updated_at": result.updated_at,
    }


def _chapter_payload(description: str) -> list[dict]:
    return extract_chapters(description)


async def _require_job(db: AsyncSession, job_id: uuid.UUID):
    job = await JobRepository(db).get(job_id)
    if job is None:
        raise NotFoundError("Job not found.", code=ErrorCode.JOB_NOT_FOUND)
    return job


@router.get("/{job_id}/results")
async def list_results(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    await _require_job(db, job_id)
    results = await SEOResultRepository(db).list_for_job(job_id)
    return success({"items": [_serialize(result) for result in results]})


@router.get("/{job_id}/results/current")
async def current_result(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    job = await _require_job(db, job_id)
    result = await SEOResultRepository(db).get_current(job_id)
    if result is None:
        return success(
            {
                "result": None,
                "job_status": job.status,
                "message": "No SEO result has been generated for this job yet.",
            }
        )
    return success({"result": _serialize(result), "job_status": job.status})


@router.get("/{job_id}/results/{result_id}")
async def get_result(job_id: uuid.UUID, result_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    await _require_job(db, job_id)
    result = await SEOResultRepository(db).get(result_id)
    if result is None or result.job_id != job_id:
        raise NotFoundError("SEO result not found.", code=ErrorCode.SEO_RESULT_NOT_FOUND)
    return success(_serialize(result))


@router.patch("/{job_id}/results/{result_id}")
async def update_result(
    job_id: uuid.UUID,
    result_id: uuid.UUID,
    payload: SEOResultUpdate,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Manual edit. Validates first, never triggers a Gemini request."""
    await _require_job(db, job_id)
    repo = SEOResultRepository(db)
    result = await repo.get(result_id)
    if result is None or result.job_id != job_id:
        raise NotFoundError("SEO result not found.", code=ErrorCode.SEO_RESULT_NOT_FOUND)

    values = payload.model_dump(exclude_none=True)
    merged = {
        "title": values.get("title", result.title),
        "description": values.get("description", result.description),
        "tags": values.get("tags", result.tags),
        "seo_score": values.get("seo_score", result.seo_score),
        "improvement_suggestions": values.get("improvement_suggestions", result.improvement_suggestions),
        "thumbnail_prompt": values.get("thumbnail_prompt", result.thumbnail_prompt),
    }

    job = await _require_job(db, job_id)
    validator = SEOValidator(
        video_duration_seconds=job.video_duration_seconds,
        allowed_chapter_timestamps=[
            float(topic.get("start_seconds", 0)) for topic in (job.timeline_snapshot or [])
        ]
        or None,
        allowed_chapter_windows=[
            (float(topic.get("start_seconds", 0)), float(topic.get("end_seconds", 0)))
            for topic in (job.timeline_snapshot or [])
        ]
        or None,
    )
    cleaned, metadata = validator.validate(merged)
    metadata["manual_edit"] = True

    updated = await repo.update_fields(
        result,
        title=cleaned.title,
        description=cleaned.description,
        tags=cleaned.tags,
        improvement_suggestions=cleaned.improvement_suggestions,
        thumbnail_prompt=cleaned.thumbnail_prompt,
        validation_metadata={**(result.validation_metadata or {}), "last_manual_validation": metadata},
        chapters=metadata["chapter_validation"]["chapters"],
    )
    return success(_serialize(updated), message="SEO result saved.")


@router.post("/{job_id}/results/{result_id}/restore")
async def restore_result(job_id: uuid.UUID, result_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    """Restore an older version as current - newer versions are preserved."""
    await _require_job(db, job_id)
    repo = SEOResultRepository(db)
    result = await repo.get(result_id)
    if result is None or result.job_id != job_id:
        raise NotFoundError("SEO result not found.", code=ErrorCode.SEO_RESULT_NOT_FOUND)
    restored = await repo.set_current(job_id, result_id)
    if restored is None:
        raise SEOValidationError("The version could not be restored.")
    return success(_serialize(restored), message=f"Version {restored.version_number} is now current.")


@router.post("/{job_id}/results/validate")
async def validate_description(job_id: uuid.UUID, payload: dict, db: AsyncSession = Depends(get_db)) -> dict:
    """Live chapter validation for the description editor (no write)."""
    job = await _require_job(db, job_id)
    description = str(payload.get("description") or "")
    report = validate_chapters(
        description,
        video_duration_seconds=job.video_duration_seconds,
        allowed_timestamps=[float(topic.get("start_seconds", 0)) for topic in (job.timeline_snapshot or [])]
        or None,
        allowed_windows=[
            (float(topic.get("start_seconds", 0)), float(topic.get("end_seconds", 0)))
            for topic in (job.timeline_snapshot or [])
        ]
        or None,
    )
    return success(
        {
            "valid": report["valid"],
            "checks": report["checks"],
            "issues": report["issues"],
            "chapters": report["chapters"],
            "description_length": len(description),
        }
    )
