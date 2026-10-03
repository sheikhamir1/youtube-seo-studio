"""Async FFmpeg / FFprobe process helpers.

Structured argument lists only - never a shell string built from user input
(no ``shell=True`` anywhere in the codebase).
"""

from __future__ import annotations

import asyncio
import json
import shutil
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from app.core.config import settings
from app.core.errors import ErrorCode, FFmpegError
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ProcessResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""
    progress_samples: list[float] = field(default_factory=list)


def binary_available(name: str) -> bool:
    return shutil.which(name) is not None


def ensure_binaries() -> None:
    """Fail fast with a clear message when FFmpeg is not installed."""
    if not binary_available(settings.ffmpeg_binary):
        raise FFmpegError(
            "FFmpeg is not installed or not on PATH. Install FFmpeg and ensure `ffmpeg` is available.",
            code=ErrorCode.FFMPEG_NOT_FOUND,
            http_status=503,
        )
    if not binary_available(settings.ffprobe_binary):
        raise FFmpegError(
            "FFprobe is not installed or not on PATH. Install FFmpeg and ensure `ffprobe` is available.",
            code=ErrorCode.FFPROBE_NOT_FOUND,
            http_status=503,
        )


async def run_ffprobe(args: Sequence[str], *, timeout: float = 120.0) -> dict:
    """Run ffprobe with JSON output and return the parsed payload."""
    if not binary_available(settings.ffprobe_binary):
        raise FFmpegError(
            "FFprobe is not installed or not on PATH.",
            code=ErrorCode.FFPROBE_NOT_FOUND,
            http_status=503,
        )
    process = await asyncio.create_subprocess_exec(
        settings.ffprobe_binary,
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except TimeoutError as exc:
        process.kill()
        raise FFmpegError(
            "FFprobe timed out while inspecting the media file.",
            code=ErrorCode.FFPROBE_ERROR,
        ) from exc

    if process.returncode != 0:
        raise FFmpegError(
            "FFprobe could not read the media file.",
            details=(stderr or b"").decode("utf-8", "ignore")[-1500:],
            code=ErrorCode.FFPROBE_ERROR,
            http_status=422,
        )
    try:
        return json.loads((stdout or b"{}").decode("utf-8", "ignore") or "{}")
    except json.JSONDecodeError as exc:
        raise FFmpegError(
            "FFprobe returned unreadable output.",
            code=ErrorCode.FFPROBE_ERROR,
        ) from exc


async def run_ffmpeg(
    args: Sequence[str],
    *,
    timeout: float,
    total_duration_seconds: float | None = None,
    on_progress: Callable[[float], None] | None = None,
    progress_interval_seconds: float = 5.0,
) -> ProcessResult:
    """Run FFmpeg, parsing ``-progress pipe:1`` output for real progress."""
    if not binary_available(settings.ffmpeg_binary):
        raise FFmpegError(
            "FFmpeg is not installed or not on PATH.",
            code=ErrorCode.FFMPEG_NOT_FOUND,
            http_status=503,
        )

    command = [settings.ffmpeg_binary, *args]
    logger.debug("ffmpeg_start argv=%s", command[:6])

    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    samples: list[float] = []
    last_report = 0.0

    async def read_progress() -> None:
        """Consume ``-progress pipe:1`` lines (stdout) as they are produced."""
        nonlocal last_report
        assert process.stdout is not None
        async for raw_line in process.stdout:
            line = raw_line.decode("utf-8", "ignore").strip()
            if not line.startswith("out_time_ms=") or not total_duration_seconds:
                continue
            try:
                milliseconds = int(line.split("=", 1)[1])
            except ValueError:
                continue
            seconds = milliseconds / 1_000_000
            percent = max(0.0, min(100.0, (seconds / total_duration_seconds) * 100))
            samples.append(percent)
            if percent - last_report >= progress_interval_seconds and on_progress:
                last_report = percent
                on_progress(percent)

    async def read_stderr() -> str:
        """Drain stderr concurrently so FFmpeg can never block on a full pipe."""
        assert process.stderr is not None
        chunks: list[bytes] = []
        async for block in process.stderr:
            chunks.append(block)
        return b"".join(chunks).decode("utf-8", "ignore")

    # stdout carries progress, stderr carries diagnostics: both are read by
    # their own task. ``communicate()`` must NOT be used here, because it would
    # try to read the already-consumed stdout stream.
    progress_task = asyncio.create_task(read_progress())
    stderr_task = asyncio.create_task(read_stderr())
    try:
        await asyncio.wait_for(process.wait(), timeout=timeout)
        stdout_extra = b""
    except TimeoutError as exc:
        process.kill()
        await process.wait()
        raise FFmpegError(
            "FFmpeg processing timed out.",
            details=f"Timed out after {timeout:.0f}s.",
        ) from exc
    finally:
        for task in (progress_task, stderr_task):
            if not task.done():
                task.cancel()
        results = await asyncio.gather(progress_task, stderr_task, return_exceptions=True)

    stderr_text = results[1] if isinstance(results[1], str) else ""
    if process.returncode != 0:
        raise FFmpegError(
            "FFmpeg failed to process the media file.",
            details=_summarize_stderr(stderr_text),
        )

    return ProcessResult(
        returncode=process.returncode,
        stdout=(stdout_extra or b"").decode("utf-8", "ignore"),
        stderr=stderr_text,
        progress_samples=samples,
    )


def _summarize_stderr(stderr: str, *, limit: int = 1500) -> str:
    """Keep the useful tail of FFmpeg's stderr instead of dumping everything."""
    lines = [line for line in (stderr or "").splitlines() if line.strip()]
    return "\n".join(lines[-12:])[-limit:]
