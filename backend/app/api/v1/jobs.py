"""Job endpoints: create, inspect, cancel, retry, timeline, events, SSE."""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.enums import ACTIVE_JOB_STATUSES, JobStage, JobStatus
from app.core.errors import ConflictError, ErrorCode, NotFoundError
from app.core.logging import get_logger
from app.core.responses import success
from app.core.timeutils import format_duration
from app.db.dependencies import get_db
from app.db.session import session_scope
from app.repositories.ai_requests import AIRequestRepository
from app.repositories.chunks import ChunkRepository
from app.repositories.events import JobEventRepository
from app.repositories.jobs import JobRepository
from app.repositories.prompt_templates import PromptTemplateRepository
from app.repositories.results import SEOResultRepository
from app.repositories.uploads import UploadRepository
from app.schemas.job import JobCreateRequest, PreflightEstimate
from app.services.ai.model_registry import validate_model_for_audio
from app.services.ai.usage import estimate_chunk_input_tokens
from app.services.media.chunking import count_chunks
from app.services.prompts.defaults import MAP_SYSTEM_PROMPT
from app.services.prompts.renderer import validate_template_variables
from app.services.storage import StorageService

router = APIRouter(prefix="/jobs", tags=["jobs"])
logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _require_job(db: AsyncSession, job_id: uuid.UUID):
    job = await JobRepository(db).get(job_id)
    if job is None:
        raise NotFoundError("Job not found.", code=ErrorCode.JOB_NOT_FOUND)
    return job


def _pipeline_config(model: str, seo_context: dict) -> dict:
    """Freeze the settings used by this job so old jobs stay reproducible."""
    return {
        "chunk_duration_seconds": settings.chunk_duration_seconds,
        "chunk_overlap_seconds": settings.chunk_overlap_seconds,
        "audio_format": settings.audio_format,
        "gemini_min_interval_seconds": settings.gemini_min_interval_seconds,
        "model": model,
        "language": seo_context.get("content_language", "auto"),
        "max_topics_per_chunk": settings.map_max_topics_per_chunk,
        "max_retries": settings.max_gemini_retries,
        "audio_tokens_per_second": settings.audio_tokens_per_second,
    }


async def build_preflight(
    db: AsyncSession, *, duration_seconds: float | None, model: str
) -> PreflightEstimate:
    chunk_tokens = estimate_chunk_input_tokens(
        settings.chunk_duration_seconds, system_prompt=MAP_SYSTEM_PROMPT
    )
    requests_today = await AIRequestRepository(db).requests_today()
    chunk_count = count_chunks(
        duration_seconds or 0.0,
        chunk_duration=settings.chunk_duration_seconds,
        overlap=settings.chunk_overlap_seconds,
    )
    total_requests = chunk_count + 1
    exceeds = requests_today + total_requests > settings.gemini_rpd_limit
    warning = None
    if exceeds:
        warning = (
            "Estimated request usage is high compared with the configured daily Gemini "
            f"request budget ({requests_today} logged today, about {total_requests} needed)."
        )
    elif chunk_count > 12:
        warning = (
            f"This is a long video: about {total_requests} Gemini requests are expected, paced at "
            f"a minimum of {int(settings.gemini_min_interval_seconds)} seconds between requests."
        )
    return PreflightEstimate(
        duration_seconds=duration_seconds,
        duration_formatted=format_duration(duration_seconds),
        estimated_chunks=chunk_count,
        estimated_map_requests=chunk_count,
        estimated_reduce_requests=1,
        estimated_total_requests=total_requests,
        estimated_input_tokens_per_chunk=chunk_tokens,
        estimated_total_tokens=chunk_tokens * max(1, chunk_count) + 6000,
        requests_today=requests_today,
        rpd_limit=settings.gemini_rpd_limit,
        exceeds_daily_budget=exceeds,
        warning=warning,
    )


# ---------------------------------------------------------------------------
# CRUD / lifecycle
# ---------------------------------------------------------------------------
@router.get("")
async def list_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None, description="QUEUED|PROCESSING|COMPLETED|FAILED|CANCELED"),
    search: str | None = Query(None, max_length=200),
    sort: str = Query("-created_at"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    repo = JobRepository(db)
    jobs, total = await repo.list_jobs(
        page=page, page_size=page_size, status=status, search=search, sort=sort
    )
    result_repo = SEOResultRepository(db)
    scores = await result_repo.current_scores([job.id for job in jobs])

    items = [
        {
            "id": job.id,
            "original_filename": job.original_filename,
            "status": job.status,
            "stage": job.stage,
            "progress_percent": job.progress_percent,
            "selected_model": job.selected_model,
            "video_duration_seconds": job.video_duration_seconds,
            "created_at": job.created_at,
            "completed_at": job.completed_at,
            "prompt_template_name_snapshot": job.prompt_template_name_snapshot,
            "total_chunks": job.total_chunks,
            "current_seo_score": scores.get(job.id),
        }
        for job in jobs
    ]
    return success({"items": items, "total": total, "page": page, "page_size": page_size})


@router.post("", status_code=201)
async def create_job(
    payload: JobCreateRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create a job from a completed upload (idempotent per client_request_id)."""
    if payload.client_request_id:
        duplicate = await JobRepository(db).find_by_client_request_id(payload.client_request_id)
        if duplicate is not None:
            # Idempotent behaviour: the same request never creates a second job,
            # and the caller can tell the two cases apart by the status code
            # (201 created vs 200 already existed).
            response.status_code = 200
            return success(
                {
                    "id": duplicate.id,
                    "status": duplicate.status,
                    "original_filename": duplicate.original_filename,
                    "selected_model": duplicate.selected_model,
                    "prompt_template_name_snapshot": duplicate.prompt_template_name_snapshot,
                    "duplicate": True,
                },
                message="This analysis request already exists.",
            )

    upload_repo = UploadRepository(db)
    upload = await upload_repo.get(payload.upload_id)
    if upload is None:
        raise NotFoundError("The upload session was not found.", code=ErrorCode.UPLOAD_SESSION_NOT_FOUND)
    if upload.status != "COMPLETED":
        raise ConflictError(
            "The upload must be completed before a job can be created.",
            details={"upload_status": upload.status},
            code=ErrorCode.UPLOAD_INCOMPLETE,
        )

    template = await PromptTemplateRepository(db).get(payload.prompt_template_id)
    if template is None:
        raise NotFoundError(
            "The selected prompt template was not found.",
            code=ErrorCode.PROMPT_TEMPLATE_NOT_FOUND,
        )
    # Validate the template before any expensive processing starts.
    validate_template_variables(template.user_prompt_template)
    validate_model_for_audio(payload.selected_model)

    seo_context = payload.seo_context.model_dump()
    storage = StorageService()
    job = await JobRepository(db).create(
        upload_session_id=upload.id,
        original_filename=upload.original_filename,
        source_path=upload.temporary_path,  # moved into the job directory on first run
        source_size_bytes=upload.expected_size,
        status=JobStatus.QUEUED.value,
        stage=JobStage.PENDING.value,
        progress_percent=0.0,
        selected_model=payload.selected_model,
        prompt_template_id=template.id,
        prompt_template_name_snapshot=template.name,
        system_prompt_snapshot=template.system_prompt,
        user_prompt_template_snapshot=template.user_prompt_template,
        pipeline_config={
            **_pipeline_config(payload.selected_model, seo_context),
            "client_request_id": payload.client_request_id,
        },
        seo_context=seo_context,
        cancel_requested=False,
    )
    await JobEventRepository(db).append(
        job_id=job.id,
        event_type="JOB_CREATED",
        message=f"Analysis queued for '{job.original_filename}' using {template.name}",
        stage=JobStage.PENDING.value,
        payload={
            "model": payload.selected_model,
            "prompt_template": template.name,
            "seo_context": seo_context,
        },
    )
    storage.create_job_dirs(job.id)
    logger.info("job_created job_id=%s filename=%s", job.id, job.original_filename)
    return success(
        {
            "id": job.id,
            "status": job.status,
            "original_filename": job.original_filename,
            "selected_model": job.selected_model,
            "prompt_template_name_snapshot": job.prompt_template_name_snapshot,
        },
        message="Analysis queued.",
    )


@router.get("/{job_id}")
async def get_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    job = await _require_job(db, job_id)
    chunks = await ChunkRepository(db).list_for_job(job_id)
    current = await SEOResultRepository(db).get_current(job_id)
    preflight = await build_preflight(
        db, duration_seconds=job.video_duration_seconds, model=job.selected_model
    )

    return success(
        {
            "job": {
                "id": job.id,
                "upload_session_id": job.upload_session_id,
                "original_filename": job.original_filename,
                "source_size_bytes": job.source_size_bytes,
                "video_duration_seconds": job.video_duration_seconds,
                "audio_stream_index": job.audio_stream_index,
                "audio_stream_language": job.audio_stream_language,
                "audio_stream_start_offset_seconds": job.audio_stream_start_offset_seconds,
                "audio_duration_seconds": job.audio_duration_seconds,
                "status": job.status,
                "stage": job.stage,
                "progress_percent": job.progress_percent,
                "current_chunk_index": job.current_chunk_index,
                "total_chunks": job.total_chunks,
                "selected_model": job.selected_model,
                "prompt_template_id": job.prompt_template_id,
                "prompt_template_name_snapshot": job.prompt_template_name_snapshot,
                "pipeline_config": job.pipeline_config,
                "seo_context": job.seo_context,
                "current_error_code": job.current_error_code,
                "current_error_message": job.current_error_message,
                "failed_stage": job.failed_stage,
                "failed_chunk_index": job.failed_chunk_index,
                "attempt_count": job.attempt_count,
                "cancel_requested": job.cancel_requested,
                "created_at": job.created_at,
                "started_at": job.started_at,
                "completed_at": job.completed_at,
                "failed_at": job.failed_at,
                "last_heartbeat_at": job.last_heartbeat_at,
            },
            "chunks": [
                {
                    "id": chunk.id,
                    "chunk_index": chunk.chunk_index,
                    "start_seconds": chunk.start_seconds,
                    "end_seconds": chunk.end_seconds,
                    "duration_seconds": chunk.duration_seconds,
                    "status": chunk.status,
                    "attempt_count": chunk.attempt_count,
                    "estimated_input_tokens": chunk.estimated_input_tokens,
                    "actual_input_tokens": chunk.actual_input_tokens,
                    "actual_output_tokens": chunk.actual_output_tokens,
                    "error_code": chunk.error_code,
                    "error_message": chunk.error_message,
                    "created_at": chunk.created_at,
                    "completed_at": chunk.completed_at,
                }
                for chunk in chunks
            ],
            "current_result_id": current.id if current else None,
            "preflight": preflight.model_dump(),
        }
    )


@router.get("/{job_id}/summary")
async def job_summary(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    """Compact header data for the job detail page."""
    job = await _require_job(db, job_id)
    chunks = await ChunkRepository(db).list_for_job(job_id)
    current = await SEOResultRepository(db).get_current(job_id)
    ai_repo = AIRequestRepository(db)
    requests = await ai_repo.request_count_for_job(job_id)
    retries = await ai_repo.retry_count_for_job(job_id)
    input_tokens, output_tokens = await ChunkRepository(db).token_totals(job_id)
    completed_chunks = sum(1 for chunk in chunks if chunk.status == "COMPLETED")
    failed_chunks = sum(1 for chunk in chunks if chunk.status == "FAILED")

    durations = {
        "total_seconds": (job.completed_at - job.started_at).total_seconds()
        if job.completed_at and job.started_at
        else None,
    }

    return success(
        {
            "job_id": job.id,
            "filename": job.original_filename,
            "duration_seconds": job.video_duration_seconds,
            "duration_formatted": format_duration(job.video_duration_seconds),
            "created_at": job.created_at,
            "status": job.status,
            "stage": job.stage,
            "model": job.selected_model,
            "prompt_template": job.prompt_template_name_snapshot,
            "chunk_count": len(chunks),
            "gemini_requests": requests,
            "current_seo_score": current.seo_score if current else None,
            "processing_details": {
                "model": job.selected_model,
                "prompt_template_name_snapshot": job.prompt_template_name_snapshot,
                "chunk_count": len(chunks),
                "completed_chunks": completed_chunks,
                "failed_chunks": failed_chunks,
                "gemini_requests": requests,
                "retry_count": retries,
                "input_tokens": input_tokens or None,
                "output_tokens": output_tokens or None,
                "durations_seconds": durations,
                "pipeline_config": job.pipeline_config,
            },
        }
    )


@router.get("/{job_id}/chunks")
async def job_chunks(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    await _require_job(db, job_id)
    chunks = await ChunkRepository(db).list_for_job(job_id)
    return success(
        {
            "items": [
                {
                    "id": chunk.id,
                    "chunk_index": chunk.chunk_index,
                    "start_seconds": chunk.start_seconds,
                    "end_seconds": chunk.end_seconds,
                    "duration_seconds": chunk.duration_seconds,
                    "status": chunk.status,
                    "attempt_count": chunk.attempt_count,
                    "estimated_input_tokens": chunk.estimated_input_tokens,
                    "actual_input_tokens": chunk.actual_input_tokens,
                    "actual_output_tokens": chunk.actual_output_tokens,
                    "error_code": chunk.error_code,
                    "error_message": chunk.error_message,
                    "created_at": chunk.created_at,
                    "completed_at": chunk.completed_at,
                }
                for chunk in chunks
            ]
        }
    )


@router.get("/{job_id}/timeline")
async def get_timeline(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    job = await _require_job(db, job_id)
    topics = list(job.timeline_snapshot or [])
    return success(
        {
            "job_id": str(job.id),
            "video_duration_seconds": job.video_duration_seconds,
            "topic_count": len(topics),
            "topics": topics,
            "generated_at": job.updated_at.isoformat() if topics else None,
            "note": "AI-generated content timestamps (not frame-accurate).",
        }
    )


@router.get("/{job_id}/events")
async def list_events(
    job_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(200, ge=1, le=1000),
    level: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _require_job(db, job_id)
    events, total = await JobEventRepository(db).list_for_job(
        job_id, limit=page_size, offset=(page - 1) * page_size, level=level
    )
    return success(
        {
            "items": [
                {
                    "id": event.id,
                    "job_id": event.job_id,
                    "sequence_number": event.sequence_number,
                    "event_type": event.event_type,
                    "level": event.level,
                    "stage": event.stage,
                    "message": event.message,
                    "progress_percent": event.progress_percent,
                    "chunk_index": event.chunk_index,
                    "payload": event.payload,
                    "created_at": event.created_at,
                }
                for event in events
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    job = await _require_job(db, job_id)
    if job.status in (JobStatus.COMPLETED.value, JobStatus.CANCELED.value):
        raise ConflictError(
            f"This job is already {job.status.lower()}.",
            code=ErrorCode.INVALID_JOB_STATE,
        )
    updated = await JobRepository(db).request_cancel(job_id)
    await JobEventRepository(db).append(
        job_id=job_id,
        event_type="CANCEL_REQUESTED",
        level="WARNING",
        stage=updated.stage if updated else None,
        message="Cancellation requested. The worker will stop at the next safe checkpoint.",
    )
    return success(
        {"id": job_id, "status": updated.status if updated else JobStatus.CANCEL_REQUESTED.value},
        message="Cancellation requested.",
    )


@router.post("/{job_id}/retry")
async def retry_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    """Re-queue a failed/canceled job, reusing everything already completed."""
    job = await _require_job(db, job_id)
    if job.status not in (JobStatus.FAILED.value, JobStatus.CANCELED.value):
        raise ConflictError(
            "Only failed or canceled jobs can be retried.",
            details={"status": job.status},
            code=ErrorCode.INVALID_JOB_STATE,
        )
    chunk_repo = ChunkRepository(db)
    reset = await chunk_repo.reset_incomplete(job_id)
    await JobRepository(db).requeue(job_id)
    await JobEventRepository(db).append(
        job_id=job_id,
        event_type="JOB_RETRY_QUEUED",
        level="WARNING",
        stage=job.stage,
        message=(
            "Retry queued. Completed work is preserved; processing resumes from the first incomplete step."
        ),
        payload={"reset_chunks": reset},
    )
    return success({"id": job_id, "status": JobStatus.QUEUED.value}, message="Retry queued.")


@router.post("/{job_id}/regenerate")
async def regenerate_seo(
    job_id: uuid.UUID,
    payload: dict | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create a new SEO version from the stored timeline - no media work."""
    job = await _require_job(db, job_id)
    if not job.timeline_snapshot:
        raise ConflictError(
            "This job has no normalized timeline yet, so SEO cannot be regenerated.",
            code=ErrorCode.INVALID_JOB_STATE,
        )
    body = payload or {}
    template_id = body.get("prompt_template_id")
    model = body.get("selected_model")
    if model:
        validate_model_for_audio(model)

    from app.worker.dispatcher import get_orchestrator

    orchestrator = await get_orchestrator()
    result_id = await orchestrator.regenerate_seo(
        job_id=job_id,
        prompt_template_id=uuid.UUID(str(template_id)) if template_id else None,
        model=model,
    )
    return success(
        {"job_id": job_id, "result_id": result_id},
        message="New SEO version generated.",
    )


@router.delete("/{job_id}")
async def delete_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    job = await _require_job(db, job_id)
    if job.status in ACTIVE_JOB_STATUSES:
        raise ConflictError(
            "Cancel the analysis before deleting it.",
            code=ErrorCode.INVALID_JOB_STATE,
        )
    storage = StorageService()
    freed_bytes = 0
    try:
        # Remove source video, extracted audio, chunks and generated output.
        freed_bytes = storage.delete_job_files(job_id)
    except Exception as exc:
        logger.warning("job_file_delete_failed job_id=%s error=%s", job_id, exc)
    await JobRepository(db).delete(job)
    return success(
        {"id": job_id, "freed_bytes": freed_bytes},
        message="Job and its local files were deleted.",
    )


# ---------------------------------------------------------------------------
# SSE
# ---------------------------------------------------------------------------
@router.get("/{job_id}/events/stream")
async def stream_events(
    job_id: uuid.UUID,
    request: Request,
    last_event_id: str | None = Query(None, alias="last_event_id"),
) -> StreamingResponse:
    """Server-Sent Events stream: snapshot first, then live updates.

    Supports ``Last-Event-ID`` (header or ``last_event_id`` query parameter) so a
    refresh or reconnect resumes from the correct event.
    """
    async with session_scope() as session:
        job = await JobRepository(session).get(job_id)
        if job is None:
            raise NotFoundError("Job not found.", code=ErrorCode.JOB_NOT_FOUND)

    resume_from = last_event_id or request.headers.get("last-event-id")
    try:
        after_id = int(resume_from) if resume_from else 0
    except (TypeError, ValueError):
        after_id = 0

    async def event_generator():
        nonlocal after_id
        heartbeat_interval = 15.0
        idle = 0.0

        # 1) Immediately send the current snapshot (database is the source of truth).
        async with session_scope() as session:
            job = await JobRepository(session).get(job_id)
            if job is None:
                return
            payload = {
                "event": "snapshot",
                "job": {
                    "id": str(job.id),
                    "status": job.status,
                    "stage": job.stage,
                    "progress_percent": job.progress_percent,
                    "current_chunk_index": job.current_chunk_index,
                    "total_chunks": job.total_chunks,
                    "selected_model": job.selected_model,
                    "current_error_code": job.current_error_code,
                    "current_error_message": job.current_error_message,
                    "failed_stage": job.failed_stage,
                    "failed_chunk_index": job.failed_chunk_index,
                    "cancel_requested": job.cancel_requested,
                    "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                },
            }
            yield f"event: snapshot\ndata: {json.dumps(payload)}\n\n"
            if after_id == 0:
                latest = await JobEventRepository(session).latest(job_id)
                after_id = latest.id if latest else 0

        while True:
            if await request.is_disconnected():
                break

            emitted = False
            async with session_scope() as session:
                events = await JobEventRepository(session).list_after(job_id, after_id=after_id)
                job = await JobRepository(session).get(job_id)
                for event in events:
                    after_id = event.id
                    emitted = True
                    data = {
                        "event": event.event_type,
                        "level": event.level,
                        "stage": event.stage,
                        "message": event.message,
                        "progress_percent": event.progress_percent,
                        "chunk_index": event.chunk_index,
                        "created_at": event.created_at.isoformat(),
                        "payload": event.payload,
                    }
                    yield (
                        f"event: {event.event_type.lower()}\n"
                        f"id: {event.id}\n"
                        f"data: {json.dumps(data, default=str)}\n\n"
                    )

                if job is not None and (emitted or idle >= heartbeat_interval):
                    progress_data = {
                        "event": "progress",
                        "status": job.status,
                        "stage": job.stage,
                        "progress_percent": job.progress_percent,
                        "current_chunk": job.current_chunk_index,
                        "total_chunks": job.total_chunks,
                        "model": job.selected_model,
                        "cancel_requested": job.cancel_requested,
                        "error_code": job.current_error_code,
                        "error_message": job.current_error_message,
                        "failed_stage": job.failed_stage,
                        "failed_chunk_index": job.failed_chunk_index,
                    }
                    yield (
                        f"event: progress\nid: {after_id}\ndata: {json.dumps(progress_data, default=str)}\n\n"
                    )
                    idle = 0.0
                    terminal = job.status in {
                        JobStatus.COMPLETED.value,
                        JobStatus.FAILED.value,
                        JobStatus.CANCELED.value,
                    }
                    if terminal:
                        yield (f'event: done\nid: {after_id}\ndata: {{"status": "{job.status}"}}\n\n')
                        break
                else:
                    idle += 1.0
                    yield ": heartbeat\n\n"

            await asyncio.sleep(1.0)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            # Disables proxy buffering (nginx honours this too).
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{job_id}/source")
async def job_source_info(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    """Local file/directory information (no file content is exposed)."""
    job = await _require_job(db, job_id)
    paths = StorageService().job_paths(job_id)
    source = Path(job.source_path)
    return success(
        {
            "source_exists": source.exists(),
            "source_name": source.name,
            "source_size_bytes": source.stat().st_size if source.exists() else 0,
            "job_directory": str(paths.root),
            "audio_exists": (paths.audio_dir.exists() and any(paths.audio_dir.iterdir()))
            if paths.audio_dir.exists()
            else False,
            "chunk_count_on_disk": len(list(paths.chunks_dir.glob("chunk-*")))
            if paths.chunks_dir.exists()
            else 0,
            "timeline_file": str(paths.timeline_file) if paths.timeline_file.exists() else None,
        }
    )
