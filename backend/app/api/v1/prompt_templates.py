"""Prompt template CRUD (Reduce-phase templates only)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, ErrorCode, NotFoundError
from app.core.responses import success
from app.db.dependencies import get_db
from app.repositories.prompt_templates import PromptTemplateRepository
from app.schemas.prompt_template import (
    PromptTemplateCreate,
    PromptTemplatePreviewRequest,
    PromptTemplateUpdate,
)
from app.services.prompts.defaults import DEFAULT_SEO_USER_PROMPT_TEMPLATE, SUPPORTED_TEMPLATE_VARIABLES
from app.services.prompts.renderer import (
    build_seo_context_values,
    extract_template_variables,
    render_template,
    validate_template_variables,
)

router = APIRouter(prefix="/prompt-templates", tags=["prompt-templates"])

SAMPLE_TIMELINE = [
    {
        "topic": "Introduction and session overview",
        "summary": "The speaker frames the session and lists what will be covered.",
        "start_seconds": 0,
        "end_seconds": 420,
        "source_chunk_indices": [0],
    },
    {
        "topic": "Core concepts explained",
        "summary": "Definitions, terminology and a worked example.",
        "start_seconds": 420,
        "end_seconds": 2400,
        "source_chunk_indices": [0],
    },
    {
        "topic": "Practical demonstration",
        "summary": "A full walkthrough of the workflow with commentary.",
        "start_seconds": 2400,
        "end_seconds": 3900,
        "source_chunk_indices": [0],
    },
]


def _serialize(template) -> dict:
    return {
        "id": template.id,
        "name": template.name,
        "description": template.description,
        "system_prompt": template.system_prompt,
        "user_prompt_template": template.user_prompt_template,
        "is_default": template.is_default,
        "created_at": template.created_at,
        "updated_at": template.updated_at,
        "variables": sorted(extract_template_variables(template.user_prompt_template)),
    }


@router.get("")
async def list_templates(db: AsyncSession = Depends(get_db)) -> dict:
    templates = await PromptTemplateRepository(db).list_all()
    return success(
        {"items": [_serialize(template) for template in templates]},
    )


@router.get("/variables")
async def list_variables() -> dict:
    """Variables the editor may use, with preview values for the sample render."""
    return success(
        {
            "available_variables": list(SUPPORTED_TEMPLATE_VARIABLES),
            "sample_context": build_seo_context_values(
                seo_context={
                    "video_title": "Advanced RAG Course - Session 4",
                    "primary_keyword": "vector search",
                    "secondary_keywords": ["embeddings", "semantic search"],
                    "target_audience": "Developers learning retrieval systems",
                    "content_language": "Hindi/English",
                    "seo_language": "English",
                    "content_type": "Course",
                    "tone": "Educational",
                },
                original_filename="advanced-rag-session-4.mp4",
                video_duration_seconds=4320,
                timeline=SAMPLE_TIMELINE,
            ),
        }
    )


@router.get("/{template_id}")
async def get_template(template_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    template = await PromptTemplateRepository(db).get(template_id)
    if template is None:
        raise NotFoundError("Prompt template not found.", code=ErrorCode.PROMPT_TEMPLATE_NOT_FOUND)
    return success(_serialize(template))


@router.post("", status_code=201)
async def create_template(payload: PromptTemplateCreate, db: AsyncSession = Depends(get_db)) -> dict:
    repo = PromptTemplateRepository(db)
    if await repo.get_by_name(payload.name) is not None:
        raise ConflictError(
            f"A template named '{payload.name}' already exists.",
            details={"name": payload.name},
            code=ErrorCode.PROMPT_TEMPLATE_INVALID,
        )
    # Unknown variables must fail here, before any Gemini call could ever run.
    validate_template_variables(payload.user_prompt_template)
    template = await repo.create(
        name=payload.name,
        description=payload.description,
        system_prompt=payload.system_prompt,
        user_prompt_template=payload.user_prompt_template,
        is_default=False,
    )
    return success(_serialize(template), message="Template created.")


@router.patch("/{template_id}")
async def update_template(
    template_id: uuid.UUID,
    payload: PromptTemplateUpdate,
    db: AsyncSession = Depends(get_db),
) -> dict:
    repo = PromptTemplateRepository(db)
    template = await repo.get(template_id)
    if template is None:
        raise NotFoundError("Prompt template not found.", code=ErrorCode.PROMPT_TEMPLATE_NOT_FOUND)

    if payload.name and payload.name != template.name:
        clash = await repo.get_by_name(payload.name)
        if clash is not None and clash.id != template.id:
            raise ConflictError(
                f"A template named '{payload.name}' already exists.",
                code=ErrorCode.PROMPT_TEMPLATE_INVALID,
            )
    if payload.user_prompt_template:
        validate_template_variables(payload.user_prompt_template)

    updated = await repo.update(
        template,
        name=payload.name,
        description=payload.description,
        system_prompt=payload.system_prompt,
        user_prompt_template=payload.user_prompt_template,
    )
    return success(_serialize(updated), message="Template saved.")


@router.delete("/{template_id}")
async def delete_template(template_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    """Delete a template. Historical jobs keep their prompt snapshots."""
    repo = PromptTemplateRepository(db)
    template = await repo.get(template_id)
    if template is None:
        raise NotFoundError("Prompt template not found.", code=ErrorCode.PROMPT_TEMPLATE_NOT_FOUND)
    if template.is_default:
        raise ConflictError(
            "The default template cannot be deleted, because new analyses need a fallback template.",
            code=ErrorCode.PROMPT_TEMPLATE_INVALID,
        )
    await repo.delete(template)
    return success({"id": template_id}, message="Template deleted.")


@router.post("/{template_id}/duplicate", status_code=201)
async def duplicate_template(template_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    repo = PromptTemplateRepository(db)
    template = await repo.get(template_id)
    if template is None:
        raise NotFoundError("Prompt template not found.", code=ErrorCode.PROMPT_TEMPLATE_NOT_FOUND)

    base_name = f"{template.name} (copy)"
    name = base_name
    suffix = 2
    while await repo.get_by_name(name) is not None:
        name = f"{base_name} {suffix}"
        suffix += 1

    duplicate = await repo.create(
        name=name,
        description=template.description,
        system_prompt=template.system_prompt,
        user_prompt_template=template.user_prompt_template,
        is_default=False,
    )
    return success(_serialize(duplicate), message="Template duplicated.")


@router.post("/preview")
async def preview_template(payload: PromptTemplatePreviewRequest) -> dict:
    """Render a template with sample data. This never calls Gemini."""
    used = validate_template_variables(payload.user_prompt_template)
    context = build_seo_context_values(
        seo_context=dict(payload.sample_context or {}),
        original_filename="sample-video.mp4",
        video_duration_seconds=4320,
        timeline=SAMPLE_TIMELINE,
    )
    warnings: list[str] = []
    try:
        rendered = render_template(payload.user_prompt_template, context)
    except Exception as exc:
        rendered = f"[rendering error] {exc}"
        warnings.append(str(exc))

    return success(
        {
            "rendered_system_prompt": None,
            "rendered_user_prompt": rendered,
            "used_variables": sorted(used),
            "available_variables": list(SUPPORTED_TEMPLATE_VARIABLES),
            "warnings": warnings,
            "sample_default_template": DEFAULT_SEO_USER_PROMPT_TEMPLATE,
        }
    )
