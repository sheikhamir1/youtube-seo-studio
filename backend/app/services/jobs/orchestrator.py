"""JobOrchestrator: coordinates the full pipeline for one job.

    validate -> extract audio -> chunk -> Map (per chunk) -> normalize -> Reduce -> SEO version

It contains no SQL, no FFmpeg command strings and no Gemini SDK details: every
low-level concern is delegated to a dedicated service. Long external operations
never hold a database transaction open - the orchestrator uses short
``session_scope()`` blocks around each state change.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.enums import (
    AIRequestPhase,
    ChunkStatus,
    EventLevel,
    JobEventType,
    JobStage,
    JobStatus,
)
from app.core.errors import AppError, ConflictError, ErrorCode, GeminiError
from app.core.logging import clear_log_context, get_logger, set_log_context
from app.core.timeutils import format_duration, utcnow
from app.db.session import session_scope
from app.repositories.ai_requests import AIRequestRepository
from app.repositories.chunks import ChunkRepository
from app.repositories.events import JobEventRepository
from app.repositories.jobs import JobRepository
from app.repositories.prompt_templates import PromptTemplateRepository
from app.repositories.results import SEOResultRepository
from app.services.ai.client import GeminiClient
from app.services.ai.map_service import GeminiMapService
from app.services.ai.model_registry import validate_model_for_audio
from app.services.ai.rate_limiter import GeminiRateLimiter
from app.services.ai.reduce_service import GeminiReduceService
from app.services.ai.usage import estimate_chunk_input_tokens
from app.services.jobs.progress import compute_progress
from app.services.jobs.state import assert_transition, is_terminal
from app.services.media.chunking import refine_chunks_for_token_budget
from app.services.media.extraction import AudioExtractionService, chunk_filename
from app.services.media.probe import MediaProbeService
from app.services.prompts.defaults import MAP_SYSTEM_PROMPT
from app.services.prompts.renderer import build_seo_context_values
from app.services.seo.validator import SEOValidator  # noqa: F401  (documented dependency)
from app.services.storage import StorageService
from app.services.timeline.normalizer import TimelineNormalizer

logger = get_logger(__name__)


@dataclass
class PipelineResult:
    status: str
    message: str
    seo_result_id: uuid.UUID | None = None


class CancellationRequested(Exception):
    """Internal signal: the worker should stop at the next safe checkpoint."""


class JobOrchestrator:
    def __init__(
        self,
        *,
        client: GeminiClient,
        limiter: GeminiRateLimiter,
        storage: StorageService | None = None,
        probe: MediaProbeService | None = None,
        extraction: AudioExtractionService | None = None,
    ) -> None:
        self.client = client
        self.limiter = limiter
        self.storage = storage or StorageService()
        self.probe = probe or MediaProbeService()
        self.extraction = extraction
        # Chunk plan size for the current run (progress reporting).
        self._chunk_plan_count: int | None = None
        # Strong references to fire-and-forget progress tasks so the event loop
        # cannot garbage-collect them mid-flight.
        self._background_tasks: set[asyncio.Task[None]] = set()

    # ------------------------------------------------------------------ public
    async def process_job(self, job_id: uuid.UUID) -> PipelineResult:
        """Run the pipeline. Returns the terminal status; never raises for
        expected failures (the job row records the error instead)."""
        set_log_context(job_id=str(job_id))
        try:
            job_snapshot = await self._load_job(job_id)
            if job_snapshot is None:
                return PipelineResult(status=JobStatus.FAILED.value, message="Job not found.")

            entry_point = self._entry_point(job_snapshot)
            logger.info("job_processing_start entry_point=%s", entry_point)

            await self._try_run(job_id, entry_point)
            return PipelineResult(
                status=JobStatus.COMPLETED.value, message="Analysis completed successfully."
            )
        except CancellationRequested:
            await self._finalize_canceled(job_id)
            return PipelineResult(status=JobStatus.CANCELED.value, message="Analysis canceled.")
        except AppError as exc:
            await self._fail_job(job_id, exc)
            return PipelineResult(status=JobStatus.FAILED.value, message=exc.message)
        except Exception as exc:
            logger.error("job_processing_crashed: %s", exc, exc_info=True)
            await self._fail_job(
                job_id,
                AppError(
                    "An unexpected error stopped the analysis.",
                    details=exc.__class__.__name__,
                    code=ErrorCode.INTERNAL_ERROR,
                ),
            )
            return PipelineResult(status=JobStatus.FAILED.value, message=str(exc)[:200])
        finally:
            clear_log_context()

    # --------------------------------------------------------------- internals
    async def _load_job(self, job_id: uuid.UUID) -> dict[str, Any] | None:
        async with session_scope() as session:
            job = await JobRepository(session).get(job_id)
            if job is None:
                return None
            return {
                "id": job.id,
                "status": job.status,
                "stage": job.stage,
                "failed_stage": job.failed_stage,
                "source_path": job.source_path,
                "original_filename": job.original_filename,
                "selected_model": job.selected_model,
                "audio_stream_index": job.audio_stream_index,
                "audio_offset": job.audio_stream_start_offset_seconds,
                "video_duration": job.video_duration_seconds,
                "audio_duration": job.audio_duration_seconds,
                "pipeline_config": dict(job.pipeline_config or {}),
                "seo_context": dict(job.seo_context or {}),
                "prompt_template_id": job.prompt_template_id,
                "system_prompt_snapshot": job.system_prompt_snapshot,
                "user_prompt_template_snapshot": job.user_prompt_template_snapshot,
                "prompt_template_name_snapshot": job.prompt_template_name_snapshot,
            }

    def _entry_point(self, job_snapshot: dict[str, Any]) -> str:
        stage = (job_snapshot.get("stage") or "").upper()
        if stage in {JobStage.REDUCTION.value, JobStatus.REDUCING.value}:
            return "reduce"
        if stage in {JobStage.MAPPING.value, JobStatus.MAPPING.value}:
            return "map"
        if stage in {JobStage.CHUNKING.value, JobStatus.CHUNKING.value}:
            return "chunking"
        if stage in {JobStage.EXTRACTION.value, JobStatus.EXTRACTING.value}:
            return "extraction"
        return "validation"

    async def _try_run(self, job_id: uuid.UUID, entry_point: str) -> None:
        """Execute the pipeline, skipping stages whose outputs already exist."""
        if entry_point == "validation":
            await self._stage_validation(job_id)
            entry_point = "extraction"
        if entry_point in {"validation", "extraction"}:
            media = await self._stage_extraction(job_id)
            entry_point = "chunking"
        else:
            media = await self._load_media_info(job_id)

        if entry_point in {"validation", "chunking"}:
            await self._stage_chunking(job_id, media)

        await self._stage_mapping(job_id)
        await self._stage_normalization(job_id)
        await self._stage_reduce(job_id)

    # ------------------------------------------------------------- stage: probe
    async def _stage_validation(self, job_id: uuid.UUID) -> None:
        await self._set_status(job_id, JobStatus.VALIDATING, JobStage.VALIDATION, progress=0.0)
        await self._event(
            job_id,
            JobEventType.VALIDATION_STARTED,
            "Validating the uploaded media file with FFprobe",
            stage=JobStage.VALIDATION,
        )
        job = await self._load_job(job_id)
        assert job is not None
        await self._check_cancel(job_id)

        source = Path(job["source_path"])
        media = await self.probe.probe(source)

        model_profile = validate_model_for_audio(job["selected_model"])
        _ = model_profile

        async with session_scope() as session:
            repo = JobRepository(session)
            await repo.update_fields(
                job_id,
                video_duration_seconds=media.duration_seconds,
                audio_stream_index=media.selected_audio_stream.index,
                audio_stream_language=media.selected_audio_stream.language,
                audio_stream_start_offset_seconds=media.selected_audio_stream.start_time_seconds,
                audio_duration_seconds=media.selected_audio_stream.duration_seconds or media.duration_seconds,
                media_metadata=media.to_dict(),
                progress_percent=compute_progress(stage=JobStage.VALIDATION.value, stage_fraction=1.0),
                stage=JobStage.VALIDATION.value,
            )
            await JobEventRepository(session).append(
                job_id=job_id,
                event_type=JobEventType.VALIDATION_COMPLETED.value,
                level=EventLevel.SUCCESS.value,
                stage=JobStage.VALIDATION.value,
                message=(
                    f"Media validated: {format_duration(media.duration_seconds)} duration, "
                    f"audio stream {media.selected_audio_stream.index} "
                    f"({media.selected_audio_stream.codec}, "
                    f"{media.selected_audio_stream.sample_rate} Hz, "
                    f"{media.selected_audio_stream.channels} channel(s))"
                ),
                progress_percent=compute_progress(stage=JobStage.VALIDATION.value, stage_fraction=1.0),
                payload=media.to_dict(),
            )

    async def _load_media_info(self, job_id: uuid.UUID):
        """Re-probe the source when resuming a job that already passed validation."""
        job = await self._load_job(job_id)
        assert job is not None
        return await self.probe.probe(Path(job["source_path"]))

    # --------------------------------------------------------- stage: extraction
    async def _stage_extraction(self, job_id: uuid.UUID):
        await self._set_status(job_id, JobStatus.EXTRACTING, JobStage.EXTRACTION, progress=5.0)
        job = await self._load_job(job_id)
        assert job is not None
        paths = self.storage.create_job_dirs(job_id)
        audio_format = (job["pipeline_config"] or {}).get("audio_format", settings.audio_format)
        extraction = self.extraction or AudioExtractionService(audio_format=audio_format)
        output_path = paths.audio_dir / f"extracted_audio.{extraction.extension()}"

        if output_path.exists() and output_path.stat().st_size > 0:
            await self._event(
                job_id,
                JobEventType.EXTRACTION_COMPLETED,
                f"Reusing existing extracted audio ({output_path.name})",
                stage=JobStage.EXTRACTION,
            )
            return await self._load_media_info(job_id)

        await self._event(
            job_id,
            JobEventType.EXTRACTION_STARTED,
            "Extracting the audio stream locally with FFmpeg (lossless)",
            stage=JobStage.EXTRACTION,
        )
        await self._check_cancel(job_id)

        last_reported = {"value": -10.0}

        def _on_progress(percent: float) -> None:
            # Milestone events only: never flood the database with progress rows.
            if percent - last_reported["value"] < 10:
                return
            last_reported["value"] = percent
            self._schedule_event(
                job_id,
                JobEventType.EXTRACTION_PROGRESS,
                f"Audio extraction {percent:.0f}% complete",
                stage=JobStage.EXTRACTION,
                progress=compute_progress(stage=JobStage.EXTRACTION.value, stage_fraction=percent / 100),
            )

        await extraction.extract_audio(
            source_path=Path(job["source_path"]),
            output_path=output_path,
            audio_stream_index=job["audio_stream_index"],
            duration_seconds=job["video_duration"],
            on_progress=_on_progress,
        )

        await self._event(
            job_id,
            JobEventType.EXTRACTION_COMPLETED,
            f"Audio extracted to {output_path.name}",
            stage=JobStage.EXTRACTION,
            level=EventLevel.SUCCESS,
            progress=compute_progress(stage=JobStage.EXTRACTION.value, stage_fraction=1.0),
            payload={"path": str(output_path)},
        )
        return await self._load_media_info(job_id)

    # ----------------------------------------------------------- stage: chunking
    async def _stage_chunking(self, job_id: uuid.UUID, media) -> None:
        await self._set_status(job_id, JobStatus.CHUNKING, JobStage.CHUNKING, progress=20.0)
        job = await self._load_job(job_id)
        assert job is not None
        config = job["pipeline_config"] or {}
        audio_format = config.get("audio_format", settings.audio_format)
        chunk_duration = float(config.get("chunk_duration_seconds", settings.chunk_duration_seconds))
        chunk_overlap = float(config.get("chunk_overlap_seconds", settings.chunk_overlap_seconds))
        audio_duration = job["audio_duration"] or media.duration_seconds
        paths = self.storage.create_job_dirs(job_id)
        extraction = self.extraction or AudioExtractionService(audio_format=audio_format)
        audio_path = paths.audio_dir / f"extracted_audio.{extraction.extension()}"

        existing = await self._existing_completed_chunks(job_id)
        if existing:
            await self._event(
                job_id,
                JobEventType.CHUNKING_COMPLETED,
                f"Reusing {len(existing)} existing audio chunk(s) from the previous attempt",
                stage=JobStage.CHUNKING,
                level=EventLevel.SUCCESS,
            )
            async with session_scope() as session:
                await JobRepository(session).update_fields(
                    job_id, total_chunks=len(await self._all_chunks(job_id))
                )
            return

        await self._event(
            job_id,
            JobEventType.CHUNKING_STARTED,
            f"Creating overlapping audio chunks ({int(chunk_duration)}s duration, "
            f"{int(chunk_overlap)}s overlap)",
            stage=JobStage.CHUNKING,
        )

        from app.services.media.chunking import plan_chunks

        boundaries = plan_chunks(
            audio_duration,
            chunk_duration_seconds=chunk_duration,
            chunk_overlap_seconds=chunk_overlap,
        )
        # Adaptive splitting when the estimated request would exceed the safe budget.
        tokens_per_second = float(config.get("audio_tokens_per_second", settings.audio_tokens_per_second))
        boundaries = refine_chunks_for_token_budget(
            boundaries,
            chunk_overlap_seconds=chunk_overlap,
            max_safe_input_tokens=settings.max_safe_input_tokens,
            tokens_per_second=tokens_per_second,
        )
        self._chunk_plan_count = len(boundaries)

        async with session_scope() as session:
            chunk_repo = ChunkRepository(session)
            await chunk_repo.delete_for_job(job_id)
            await chunk_repo.bulk_create(
                [
                    {
                        "job_id": job_id,
                        "chunk_index": boundary.chunk_index,
                        "start_seconds": boundary.start_seconds,
                        "end_seconds": boundary.end_seconds,
                        "duration_seconds": boundary.duration_seconds,
                        "local_path": str(
                            paths.chunks_dir / chunk_filename(boundary.chunk_index, extraction.extension())
                        ),
                        "status": ChunkStatus.PENDING.value,
                        "estimated_input_tokens": estimate_chunk_input_tokens(
                            boundary.duration_seconds, system_prompt=MAP_SYSTEM_PROMPT
                        ),
                    }
                    for boundary in boundaries
                ]
            )
            await JobRepository(session).update_fields(job_id, total_chunks=len(boundaries))

        await self._event(
            job_id,
            JobEventType.CHUNKING_STARTED,
            f"Planned {len(boundaries)} audio chunk(s)",
            stage=JobStage.CHUNKING,
            payload={"chunks": [boundary.to_dict() for boundary in boundaries]},
        )

        total = len(boundaries)
        counter = {"done": 0}

        def _on_chunk_complete(boundary, path) -> None:
            counter["done"] += 1
            self._schedule_event(
                job_id,
                JobEventType.CHUNK_CREATED,
                f"Chunk {boundary.chunk_index} created "
                f"({format_duration(boundary.start_seconds)} - {format_duration(boundary.end_seconds)})",
                stage=JobStage.CHUNKING,
                progress=compute_progress(
                    stage=JobStage.CHUNKING.value, stage_fraction=counter["done"] / max(1, total)
                ),
                payload=boundary.to_dict(),
            )

        await extraction.create_chunks(
            audio_path=audio_path,
            boundaries=boundaries,
            chunks_dir=paths.chunks_dir,
            on_chunk_complete=_on_chunk_complete,
        )

        await self._event(
            job_id,
            JobEventType.CHUNKING_COMPLETED,
            f"{total} audio chunk(s) ready",
            stage=JobStage.CHUNKING,
            level=EventLevel.SUCCESS,
            progress=compute_progress(stage=JobStage.CHUNKING.value, stage_fraction=1.0),
        )

    # ------------------------------------------------------------ stage: mapping
    async def _stage_mapping(self, job_id: uuid.UUID) -> None:
        job = await self._load_job(job_id)
        assert job is not None
        async with session_scope() as session:
            chunks = await ChunkRepository(session).list_for_job(job_id)
        pending = [chunk for chunk in chunks if chunk.status != ChunkStatus.COMPLETED.value]

        await self._set_status(
            job_id,
            JobStatus.MAPPING,
            JobStage.MAPPING,
            progress=compute_progress(
                stage=JobStage.MAPPING.value,
                completed_chunks=len(chunks) - len(pending),
                total_chunks=len(chunks) or 1,
            ),
        )
        await self._event(
            job_id,
            JobEventType.MAPPING_STARTED,
            f"Analyzing {len(pending)} of {len(chunks)} audio chunk(s) with {job['selected_model']}",
            stage=JobStage.MAPPING,
            payload={"total_chunks": len(chunks), "pending_chunks": len(pending)},
        )

        if not pending:
            await self._event(
                job_id,
                JobEventType.MAPPING_STARTED,
                "All chunks already analyzed; skipping the Map phase",
                stage=JobStage.MAPPING,
                level=EventLevel.SUCCESS,
            )

        for chunk in pending:
            await self._check_cancel(job_id)
            async with session_scope() as session:
                map_service = GeminiMapService(
                    client=self.client,
                    limiter=self.limiter,
                    ai_repo=AIRequestRepository(session),
                    chunk_repo=ChunkRepository(session),
                    event_repo=JobEventRepository(session),
                    model=job["selected_model"],
                    audio_start_offset_seconds=job["audio_offset"] or 0.0,
                    content_language=(job["seo_context"] or {}).get("content_language", "auto"),
                )
                try:
                    await map_service.analyze_chunk(job_id=job_id, chunk=chunk)
                except GeminiError as exc:
                    await ChunkRepository(session).mark_failed(chunk.id, code=exc.code, message=exc.message)
                    raise

            completed, total = await self._chunk_progress(job_id)
            async with session_scope() as session:
                await JobRepository(session).update_fields(
                    job_id,
                    current_chunk_index=chunk.chunk_index,
                    progress_percent=compute_progress(
                        stage=JobStage.MAPPING.value, completed_chunks=completed, total_chunks=total
                    ),
                    last_heartbeat_at=utcnow(),
                )

    # -------------------------------------------------------- stage: normalizing
    async def _stage_normalization(self, job_id: uuid.UUID) -> None:
        await self._check_cancel(job_id)
        job = await self._load_job(job_id)
        assert job is not None
        async with session_scope() as session:
            chunks = await ChunkRepository(session).list_for_job(job_id)

        chunk_results = [
            {
                "chunk_index": chunk.chunk_index,
                "start_seconds": chunk.start_seconds,
                "audio_start_offset": job["audio_offset"] or 0.0,
                "duration_seconds": chunk.duration_seconds,
                "topics": (chunk.relative_result or {}).get("topics", []),
            }
            for chunk in chunks
            if chunk.status == ChunkStatus.COMPLETED.value
        ]

        normalizer = TimelineNormalizer(
            similarity_threshold=settings.timeline_similarity_threshold,
            proximity_seconds=settings.timeline_proximity_seconds,
            video_duration_seconds=job["video_duration"],
        )
        timeline = normalizer.normalize(chunk_results)

        paths = self.storage.create_job_dirs(job_id)
        self.storage.write_json(paths.timeline_file, timeline)
        self.storage.write_json(paths.root / "output" / "raw_chunk_topics.json", chunk_results)

        async with session_scope() as session:
            await JobRepository(session).update_fields(job_id, timeline_snapshot=timeline)
            await JobEventRepository(session).append(
                job_id=job_id,
                event_type=JobEventType.TIMELINE_NORMALIZED.value,
                level=EventLevel.SUCCESS.value,
                stage=JobStage.MAPPING.value,
                message=(
                    f"Timeline built from {len(chunk_results)} chunk result(s): "
                    f"{len(timeline)} normalized topic(s) after overlap deduplication"
                ),
                payload={"topics": len(timeline), "source_chunks": len(chunk_results)},
            )

    # ------------------------------------------------------------- stage: reduce
    async def _stage_reduce(self, job_id: uuid.UUID) -> None:
        await self._set_status(job_id, JobStatus.REDUCING, JobStage.REDUCTION, progress=85.0)
        job = await self._load_job(job_id)
        assert job is not None
        await self._check_cancel(job_id)

        async with session_scope() as session:
            job_row = await JobRepository(session).get(job_id)
            assert job_row is not None
            timeline = list(job_row.timeline_snapshot or [])

        if not timeline:
            raise AppError(
                "No timeline topics were produced, so SEO assets cannot be generated.",
                code=ErrorCode.SEO_VALIDATION_ERROR,
                http_status=422,
            )

        system_prompt = job["system_prompt_snapshot"]
        user_prompt_template = job["user_prompt_template_snapshot"]
        if not system_prompt or not user_prompt_template:
            raise AppError(
                "The prompt template snapshot for this job is missing, so the Reduce phase cannot run.",
                code=ErrorCode.PROMPT_TEMPLATE_INVALID,
                http_status=422,
            )

        context_values = build_seo_context_values(
            seo_context=job["seo_context"] or {},
            original_filename=job["original_filename"],
            video_duration_seconds=job["video_duration"],
            timeline=timeline,
        )

        async with session_scope() as session:
            reduce_service = GeminiReduceService(
                client=self.client,
                limiter=self.limiter,
                ai_repo=AIRequestRepository(session),
                event_repo=JobEventRepository(session),
                model=job["selected_model"],
            )
            output, metadata, usage = await reduce_service.generate_seo(
                job_id=job_id,
                timeline=timeline,
                context_values=context_values,
                system_prompt=system_prompt,
                user_prompt_template=user_prompt_template,
                video_duration_seconds=job["video_duration"],
            )

            result_repo = SEOResultRepository(session)
            version_number = await result_repo.next_version_number(job_id)
            await result_repo.create_version(
                job_id=job_id,
                version_number=version_number,
                title=output.title,
                description=output.description,
                tags=output.tags,
                seo_score=output.seo_score,
                improvement_suggestions=output.improvement_suggestions,
                thumbnail_prompt=output.thumbnail_prompt,
                model=job["selected_model"],
                prompt_template_id=job["prompt_template_id"],
                prompt_template_name_snapshot=job["prompt_template_name_snapshot"],
                raw_response=metadata.get("raw_payload"),
                validation_metadata=metadata,
                chapters=metadata.get("chapter_validation", {}).get("chapters"),
                is_current=True,
            )
            await JobEventRepository(session).append(
                job_id=job_id,
                event_type=JobEventType.SEO_VERSION_CREATED.value,
                level=EventLevel.SUCCESS.value,
                stage=JobStage.REDUCTION.value,
                message=f"SEO version {version_number} created (score {output.seo_score}/100)",
                payload={
                    "version": version_number,
                    "seo_score": output.seo_score,
                    "input_tokens": usage.get("input_tokens"),
                    "output_tokens": usage.get("output_tokens"),
                },
            )

        # Persist the generated SEO result next to the timeline for local use.
        paths = self.storage.create_job_dirs(job_id)
        self.storage.write_json(
            paths.seo_result_file(version_number),
            {
                "version_number": version_number,
                "title": output.title,
                "description": output.description,
                "tags": output.tags,
                "seo_score": output.seo_score,
                "improvement_suggestions": output.improvement_suggestions,
                "thumbnail_prompt": output.thumbnail_prompt,
                "model": job["selected_model"],
                "prompt_template": job["prompt_template_name_snapshot"],
                "validation_metadata": metadata,
                "generated_at": utcnow().isoformat(),
            },
        )

        async with session_scope() as session:
            repo = JobRepository(session)
            await repo.update_fields(
                job_id,
                status=JobStatus.COMPLETED.value,
                stage=JobStage.COMPLETED.value,
                progress_percent=100.0,
                completed_at=utcnow(),
                current_error_code=None,
                current_error_message=None,
                failed_stage=None,
                failed_chunk_index=None,
            )
            await JobEventRepository(session).append(
                job_id=job_id,
                event_type=JobEventType.JOB_COMPLETED.value,
                level=EventLevel.SUCCESS.value,
                stage=JobStage.COMPLETED.value,
                message="Analysis completed. SEO assets are ready.",
                progress_percent=100.0,
            )

    # ------------------------------------------------------------------ helpers
    async def _set_status(
        self,
        job_id: uuid.UUID,
        status: JobStatus,
        stage: JobStage,
        *,
        progress: float | None = None,
    ) -> None:
        async with session_scope() as session:
            repo = JobRepository(session)
            job = await repo.get(job_id)
            if job is None:
                raise ConflictError("Job not found.", code=ErrorCode.JOB_NOT_FOUND, http_status=404)
            if is_terminal(job.status) and status != JobStatus.CANCELED:
                raise ConflictError(
                    f"Job is already {job.status}; it cannot move to {status.value}.",
                    code=ErrorCode.INVALID_JOB_STATE,
                )
            assert_transition(job.status, status.value)
            values: dict[str, Any] = {
                "status": status.value,
                "stage": stage.value,
                "last_heartbeat_at": utcnow(),
            }
            if progress is not None:
                values["progress_percent"] = progress
            await repo.update_fields(job_id, **values)
        set_log_context(job_id=str(job_id), stage=stage.value)

    async def _event(
        self,
        job_id: uuid.UUID,
        event_type: JobEventType,
        message: str,
        *,
        stage: JobStage | str,
        level: EventLevel = EventLevel.INFO,
        progress: float | None = None,
        payload: dict[str, Any] | None = None,
        chunk_index: int | None = None,
    ) -> None:
        stage_value = stage.value if isinstance(stage, JobStage) else str(stage)
        async with session_scope() as session:
            await JobEventRepository(session).append(
                job_id=job_id,
                event_type=event_type.value,
                level=level.value,
                stage=stage_value,
                message=message,
                progress_percent=progress,
                chunk_index=chunk_index,
                payload=payload,
            )
        self.storage.append_event_log(
            job_id,
            {
                "ts": utcnow().isoformat(),
                "type": event_type.value,
                "level": level.value,
                "stage": stage_value,
                "message": message,
                "chunk_index": chunk_index,
            },
        )

    def _schedule_event(self, *args: Any, **kwargs: Any) -> None:
        """Fire-and-forget event write used from synchronous FFmpeg callbacks."""

        async def _runner() -> None:
            try:
                await self._event(*args, **kwargs)
            except Exception as exc:
                logger.warning("event_write_failed error=%s", str(exc)[:200])

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:  # pragma: no cover - always inside a loop in practice
            return
        task = loop.create_task(_runner())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def _check_cancel(self, job_id: uuid.UUID) -> None:
        """Cancellation checkpoints: before a chunk, before Reduce, between retries."""
        async with session_scope() as session:
            job = await JobRepository(session).get(job_id)
            if job is None:
                raise CancellationRequested()
            if job.cancel_requested or job.status == JobStatus.CANCEL_REQUESTED.value:
                if job.status != JobStatus.CANCEL_REQUESTED.value:
                    await JobRepository(session).update_fields(
                        job_id, status=JobStatus.CANCEL_REQUESTED.value
                    )
                raise CancellationRequested()

    async def _all_chunks(self, job_id: uuid.UUID) -> list[Any]:
        async with session_scope() as session:
            return await ChunkRepository(session).list_for_job(job_id)

    async def _existing_completed_chunks(self, job_id: uuid.UUID) -> list[Any]:
        chunks = await self._all_chunks(job_id)
        completed = [chunk for chunk in chunks if chunk.status == ChunkStatus.COMPLETED.value]
        # Only trust completed chunks whose files still exist on disk.
        return [chunk for chunk in completed if Path(chunk.local_path).exists()]

    async def _chunk_progress(self, job_id: uuid.UUID) -> tuple[int, int]:
        async with session_scope() as session:
            chunks = await ChunkRepository(session).list_for_job(job_id)
        completed = sum(1 for chunk in chunks if chunk.status == ChunkStatus.COMPLETED.value)
        return completed, len(chunks)

    async def _fail_job(self, job_id: uuid.UUID, error: AppError) -> None:
        async with session_scope() as session:
            job = await JobRepository(session).get(job_id)
            if job is None:
                return
            stage = job.stage if job.stage not in {JobStage.COMPLETED.value} else JobStage.FAILED.value
            chunk_index = None
            if job.status in {JobStatus.MAPPING.value, JobStatus.REDUCING.value}:
                chunk_index = job.current_chunk_index
            job_status = JobStatus.FAILED.value
            if job.status == JobStatus.CANCEL_REQUESTED.value:
                job_status = JobStatus.CANCELED.value

            await JobRepository(session).update_fields(
                job_id,
                status=job_status,
                stage=JobStage.FAILED.value
                if job_status == JobStatus.FAILED.value
                else JobStage.CANCELED.value,
                failed_stage=stage,
                failed_chunk_index=chunk_index,
                failed_at=utcnow(),
                current_error_code=error.code,
                current_error_message=error.message,
            )
            await JobEventRepository(session).append(
                job_id=job_id,
                event_type=JobEventType.JOB_FAILED.value,
                level=EventLevel.ERROR.value,
                stage=stage,
                message=error.message,
                chunk_index=chunk_index,
                payload={"error_code": error.code, "details": error.details},
            )
        logger.error("job_failed code=%s message=%s", error.code, error.message)

    async def _finalize_canceled(self, job_id: uuid.UUID) -> None:
        async with session_scope() as session:
            await JobRepository(session).update_fields(
                job_id,
                status=JobStatus.CANCELED.value,
                stage=JobStage.CANCELED.value,
                cancel_requested=True,
                completed_at=None,
            )
            await JobEventRepository(session).append(
                job_id=job_id,
                event_type=JobEventType.JOB_CANCELED.value,
                level=EventLevel.WARNING.value,
                stage=JobStage.CANCELED.value,
                message="Analysis canceled by the user.",
            )
        logger.info("job_canceled job_id=%s", job_id)

    # ------------------------------------------------------------- SEO regen
    async def regenerate_seo(
        self,
        *,
        job_id: uuid.UUID,
        prompt_template_id: uuid.UUID | None = None,
        model: str | None = None,
    ) -> uuid.UUID:
        """Create a new SEO version from the stored timeline (no media work)."""
        async with session_scope() as session:
            job_row = await JobRepository(session).get(job_id)
            if job_row is None:
                raise ConflictError("Job not found.", code=ErrorCode.JOB_NOT_FOUND, http_status=404)
            timeline = list(job_row.timeline_snapshot or [])
            if not timeline:
                raise ConflictError(
                    "This job has no normalized timeline yet, so SEO cannot be regenerated.",
                    code=ErrorCode.INVALID_JOB_STATE,
                )

            template_id = prompt_template_id or job_row.prompt_template_id
            system_prompt = job_row.system_prompt_snapshot
            user_template = job_row.user_prompt_template_snapshot
            template_name = job_row.prompt_template_name_snapshot

            if prompt_template_id and prompt_template_id != job_row.prompt_template_id:
                template = await PromptTemplateRepository(session).get(prompt_template_id)
                if template is None:
                    raise ConflictError(
                        "The selected prompt template no longer exists.",
                        code=ErrorCode.PROMPT_TEMPLATE_NOT_FOUND,
                    )
                system_prompt = template.system_prompt
                user_template = template.user_prompt_template
                template_name = template.name
            elif not system_prompt or not user_template:
                template = await PromptTemplateRepository(session).get_default()
                if template is None:
                    raise ConflictError(
                        "No prompt template is available.",
                        code=ErrorCode.PROMPT_TEMPLATE_NOT_FOUND,
                    )
                system_prompt = template.system_prompt
                user_template = template.user_prompt_template
                template_id = template.id
                template_name = template.name

            selected_model = model or job_row.selected_model
            validate_model_for_audio(selected_model)

            context_values = build_seo_context_values(
                seo_context=dict(job_row.seo_context or {}),
                original_filename=job_row.original_filename,
                video_duration_seconds=job_row.video_duration_seconds,
                timeline=timeline,
            )

            reduce_service = GeminiReduceService(
                client=self.client,
                limiter=self.limiter,
                ai_repo=AIRequestRepository(session),
                event_repo=JobEventRepository(session),
                model=selected_model,
            )
            output, metadata, usage = await reduce_service.generate_seo(
                job_id=job_id,
                timeline=timeline,
                context_values=context_values,
                system_prompt=system_prompt,
                user_prompt_template=user_template,
                video_duration_seconds=job_row.video_duration_seconds,
            )

            result_repo = SEOResultRepository(session)
            version_number = await result_repo.next_version_number(job_id)
            result = await result_repo.create_version(
                job_id=job_id,
                version_number=version_number,
                title=output.title,
                description=output.description,
                tags=output.tags,
                seo_score=output.seo_score,
                improvement_suggestions=output.improvement_suggestions,
                thumbnail_prompt=output.thumbnail_prompt,
                model=selected_model,
                prompt_template_id=template_id,
                prompt_template_name_snapshot=template_name,
                raw_response=metadata.get("raw_payload"),
                validation_metadata=metadata,
                chapters=metadata.get("chapter_validation", {}).get("chapters"),
                is_current=True,
            )
            await JobEventRepository(session).append(
                job_id=job_id,
                event_type=JobEventType.SEO_VERSION_CREATED.value,
                level=EventLevel.SUCCESS.value,
                stage=JobStage.REDUCTION.value,
                message=(
                    f"SEO version {version_number} regenerated with template "
                    f"'{template_name}' (score {output.seo_score}/100)"
                ),
                payload={
                    "version": version_number,
                    "template": template_name,
                    "model": selected_model,
                    "input_tokens": usage.get("input_tokens"),
                },
            )
            paths = self.storage.create_job_dirs(job_id)
            self.storage.write_json(
                paths.seo_result_file(version_number),
                {
                    "version_number": version_number,
                    "title": output.title,
                    "description": output.description,
                    "tags": output.tags,
                    "seo_score": output.seo_score,
                    "improvement_suggestions": output.improvement_suggestions,
                    "thumbnail_prompt": output.thumbnail_prompt,
                    "model": selected_model,
                    "prompt_template": template_name,
                    "validation_metadata": metadata,
                },
            )
        return result.id


__all__ = ["AIRequestPhase", "CancellationRequested", "JobOrchestrator", "PipelineResult"]
