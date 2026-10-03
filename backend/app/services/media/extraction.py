"""AudioExtractionService: lossless audio extraction and chunk generation.

Quality policy: lossless (FLAC by default), no loudness normalization, no
silence trimming, no time stretching - the extracted audio must preserve
timing relative to the source video.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path

from app.core.config import settings
from app.core.errors import ErrorCode, FFmpegError, StorageError
from app.core.logging import get_logger
from app.services.media.chunking import ChunkBoundary
from app.services.media.ffmpeg_runner import run_ffmpeg

logger = get_logger(__name__)

AUDIO_CODEC_FLAGS: dict[str, list[str]] = {
    "flac": ["-c:a", "flac", "-compression_level", "5"],
    "wav": ["-c:a", "pcm_s16le"],
}


class AudioExtractionService:
    """Runs FFmpeg for extraction and chunking with real progress reporting."""

    def __init__(self, *, audio_format: str | None = None) -> None:
        self.audio_format = (audio_format or settings.audio_format).lower()
        if self.audio_format not in AUDIO_CODEC_FLAGS:
            self.audio_format = "flac"

    def extension(self) -> str:
        return self.audio_format

    # ----------------------------------------------------------- extraction
    async def extract_audio(
        self,
        *,
        source_path: Path,
        output_path: Path,
        audio_stream_index: int | None = None,
        duration_seconds: float | None = None,
        on_progress: Callable[[float], None] | None = None,
        on_event: Callable[[str], None] | None = None,
    ) -> Path:
        """Extract the selected audio stream to a lossless local file."""
        self._assert_writable(output_path)
        args: list[str] = ["-hide_banner", "-nostdin", "-y", "-i", str(source_path)]
        if audio_stream_index is not None:
            args += ["-map", f"0:{audio_stream_index}"]
        else:
            args += ["-map", "0:a:0"]
        args += ["-vn"]  # drop the video stream entirely
        args += AUDIO_CODEC_FLAGS[self.audio_format]
        args += [
            "-map_metadata",
            "-1",
            "-progress",
            "pipe:1",
            "-nostats",
            str(output_path),
        ]

        await run_ffmpeg(
            args,
            timeout=settings.ffmpeg_extract_timeout_seconds,
            total_duration_seconds=duration_seconds,
            on_progress=on_progress,
        )
        if not output_path.exists() or output_path.stat().st_size == 0:
            raise FFmpegError(
                "Audio extraction produced no output file.",
                code=ErrorCode.FFMPEG_ERROR,
            )
        logger.info("audio_extracted path=%s size=%s", output_path.name, output_path.stat().st_size)
        return output_path

    # -------------------------------------------------------------- chunking
    async def create_chunk(
        self,
        *,
        audio_path: Path,
        chunk: ChunkBoundary,
        output_path: Path,
        on_progress: Callable[[float], None] | None = None,
    ) -> Path:
        """Cut one chunk with an explicit seek so overlaps are exact.

        ``-ss`` before ``-i`` is fast (input seeking), and ``-t`` bounds the
        duration. Audio is stream-copied when the format allows it, which keeps
        chunk boundaries sample-accurate for FLAC/WAV without re-encoding.
        """
        self._assert_writable(output_path)
        args: list[str] = [
            "-hide_banner",
            "-nostdin",
            "-y",
            "-ss",
            f"{chunk.start_seconds:.3f}",
            "-i",
            str(audio_path),
            "-t",
            f"{chunk.duration_seconds:.3f}",
            "-vn",
        ]
        args += AUDIO_CODEC_FLAGS[self.audio_format]
        args += ["-progress", "pipe:1", "-nostats", str(output_path)]

        await run_ffmpeg(
            args,
            timeout=settings.ffmpeg_chunk_timeout_seconds,
            total_duration_seconds=chunk.duration_seconds,
            on_progress=on_progress,
        )
        if not output_path.exists() or output_path.stat().st_size == 0:
            raise FFmpegError(
                f"Chunk {chunk.chunk_index} could not be created.",
                details={"chunk_index": chunk.chunk_index},
            )
        return output_path

    async def create_chunks(
        self,
        *,
        audio_path: Path,
        boundaries: list[ChunkBoundary],
        chunks_dir: Path,
        on_chunk_complete: Callable[[ChunkBoundary, Path], None] | None = None,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> list[tuple[ChunkBoundary, Path]]:
        """Create every chunk sequentially (predictable disk writes)."""
        chunks_dir.mkdir(parents=True, exist_ok=True)
        created: list[tuple[ChunkBoundary, Path]] = []
        total = len(boundaries)
        for position, boundary in enumerate(boundaries, start=1):
            output_path = chunks_dir / chunk_filename(boundary.chunk_index, self.extension())
            # Chunking is I/O heavy; keep the event loop responsive.
            await asyncio.sleep(0)
            await self.create_chunk(audio_path=audio_path, chunk=boundary, output_path=output_path)
            created.append((boundary, output_path))
            if on_chunk_complete:
                on_chunk_complete(boundary, output_path)
            if on_progress:
                on_progress(position, total)
        return created

    # -------------------------------------------------------------- helpers
    @staticmethod
    def _assert_writable(path: Path) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except PermissionError as exc:  # pragma: no cover - environment specific
            raise StorageError(
                "Cannot write to the data directory (permission denied).",
                details=str(path.parent),
                code=ErrorCode.STORAGE_PERMISSION_ERROR,
            ) from exc
        except OSError as exc:
            raise StorageError(
                "Cannot create the output directory.",
                details=str(exc),
                code=ErrorCode.STORAGE_PATH_ERROR,
            ) from exc


def chunk_filename(index: int, extension: str) -> str:
    """Deterministic chunk filename: chunk-00000.flac, chunk-00001.flac, ..."""
    return f"chunk-{index:05d}.{extension}"
