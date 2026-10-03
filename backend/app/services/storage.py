"""Job filesystem layout and storage reporting.

Layout (per spec section 13)::

    data/jobs/<job_uuid>/
      source/original_video.ext
      audio/extracted_audio.flac
      chunks/chunk-00000.flac
      output/normalized_timeline.json
      output/seo-result-v001.json
      logs/processing.jsonl

Directories are always UUID-based; a user filename never becomes a path.
"""

from __future__ import annotations

import contextlib
import json
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.errors import ErrorCode, StorageError
from app.core.logging import get_logger
from app.core.security import disk_usage, ensure_within_directory, sanitize_filename

logger = get_logger(__name__)


@dataclass
class JobPaths:
    root: Path
    source_dir: Path
    audio_dir: Path
    chunks_dir: Path
    output_dir: Path
    logs_dir: Path

    @property
    def source_file(self) -> Path:
        """The single file inside ``source/`` (unknown extension is preserved)."""
        if not self.source_dir.exists():
            return self.source_dir / "original_video"
        files = [path for path in self.source_dir.iterdir() if path.is_file()]
        return files[0] if files else self.source_dir / "original_video"

    @property
    def timeline_file(self) -> Path:
        return self.output_dir / "normalized_timeline.json"

    @property
    def event_log_file(self) -> Path:
        return self.logs_dir / "processing.jsonl"

    @property
    def extracted_audio_file(self) -> Path:
        return self.audio_dir / f"extracted_audio.{settings.audio_format}"

    def seo_result_file(self, version_number: int) -> Path:
        return self.output_dir / f"seo-result-v{version_number:03d}.json"


class StorageService:
    """Creates and maintains the per-job directory tree."""

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = (data_dir or settings.data_dir).expanduser().resolve()
        self.jobs_dir = self.data_dir / "jobs"
        self.uploads_dir = self.data_dir / "uploads"

    def ensure_root(self) -> None:
        for directory in (self.data_dir, self.jobs_dir, self.uploads_dir):
            directory.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------------- job paths
    def job_paths(self, job_id: uuid.UUID | str) -> JobPaths:
        root = ensure_within_directory(self.jobs_dir / str(job_id), self.data_dir)
        return JobPaths(
            root=root,
            source_dir=root / "source",
            audio_dir=root / "audio",
            chunks_dir=root / "chunks",
            output_dir=root / "output",
            logs_dir=root / "logs",
        )

    def create_job_dirs(self, job_id: uuid.UUID | str) -> JobPaths:
        paths = self.job_paths(job_id)
        for directory in (
            paths.root,
            paths.source_dir,
            paths.audio_dir,
            paths.chunks_dir,
            paths.output_dir,
            paths.logs_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        return paths

    def upload_temp_path(self, upload_id: uuid.UUID | str, filename: str) -> Path:
        """Temporary location for a streaming upload (UUID directory + safe name)."""
        directory = ensure_within_directory(self.uploads_dir / str(upload_id), self.data_dir)
        directory.mkdir(parents=True, exist_ok=True)
        safe_name = sanitize_filename(filename)
        return directory / f"blob-{safe_name}"

    def move_upload_into_job(self, *, upload_path: Path, job_id: uuid.UUID, filename: str) -> Path:
        """Move a completed upload into the job's source directory."""
        if not upload_path.exists():
            raise StorageError(
                "The uploaded file could not be found.",
                code=ErrorCode.MEDIA_NOT_FOUND,
                http_status=404,
            )
        paths = self.create_job_dirs(job_id)
        safe_name = sanitize_filename(filename)
        destination = ensure_within_directory(paths.source_dir / safe_name, self.data_dir)
        shutil.move(str(upload_path), str(destination))
        # Upload folder is now empty: remove it (best effort).
        with contextlib.suppress(OSError):
            upload_path.parent.rmdir()
        logger.info("upload_moved job_id=%s size=%s", job_id, destination.stat().st_size)
        return destination

    # ---------------------------------------------------------------- artifacts
    def write_json(self, path: Path, payload: Any) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def append_event_log(self, job_id: uuid.UUID | str, event: dict[str, Any]) -> None:
        """Mirror important events into ``logs/processing.jsonl`` for debugging."""
        try:
            paths = self.job_paths(job_id)
            paths.logs_dir.mkdir(parents=True, exist_ok=True)
            with paths.event_log_file.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        except OSError as exc:  # logging must never break processing
            logger.warning("event_log_write_failed job_id=%s error=%s", job_id, exc)

    def delete_job_files(self, job_id: uuid.UUID | str) -> int:
        """Delete all files of one job. Never touches other jobs' directories."""
        paths = self.job_paths(job_id)
        if not paths.root.exists():
            return 0
        freed = self.directory_size(paths.root)
        shutil.rmtree(paths.root, ignore_errors=False)
        logger.info("job_files_deleted job_id=%s freed_bytes=%s", job_id, freed)
        return freed

    def delete_incomplete_chunks(self, job_id: uuid.UUID | str, *, keep_completed: set[int]) -> int:
        """Best-effort cleanup of chunk files that are no longer needed."""
        paths = self.job_paths(job_id)
        if not paths.chunks_dir.exists():
            return 0
        removed = 0
        for path in paths.chunks_dir.iterdir():
            if not path.is_file():
                continue
            try:
                index = int(path.stem.split("-")[-1])
            except (ValueError, IndexError):
                continue
            if index not in keep_completed:
                path.unlink(missing_ok=True)
                removed += 1
        return removed

    # ------------------------------------------------------------------ sizing
    def directory_size(self, path: Path) -> int:
        total = 0
        if not path.exists():
            return 0
        for item in path.rglob("*"):
            if item.is_file():
                try:
                    total += item.stat().st_size
                except OSError:
                    continue
        return total

    def storage_usage(self) -> dict[str, Any]:
        """Informational storage breakdown for the Settings page."""
        jobs = sorted(self.jobs_dir.glob("*")) if self.jobs_dir.exists() else []
        job_dirs = [item for item in jobs if item.is_dir()]
        source_bytes = sum(self.directory_size(item / "source") for item in job_dirs)
        audio_bytes = sum(self.directory_size(item / "audio") for item in job_dirs)
        chunk_bytes = sum(self.directory_size(item / "chunks") for item in job_dirs)
        output_bytes = sum(self.directory_size(item / "output") for item in job_dirs)
        upload_bytes = self.directory_size(self.uploads_dir)
        disk = disk_usage(self.data_dir)
        return {
            "jobs": len(job_dirs),
            "source_bytes": float(source_bytes),
            "audio_bytes": float(audio_bytes),
            "chunk_bytes": float(chunk_bytes),
            "output_bytes": float(output_bytes),
            "total_bytes": float(source_bytes + audio_bytes + chunk_bytes + output_bytes + upload_bytes),
            "available_bytes": disk["free_bytes"],
            "data_dir": str(self.data_dir),
        }
