"""Chunk planning math (pure functions - unit tested without FFmpeg).

Adjacent chunks overlap by ``chunk_overlap_seconds`` (default 60 s) so a topic
that straddles a boundary is never lost. Therefore the next chunk starts
``chunk_duration - overlap`` seconds after the previous one (default 3540 s),
NOT at the previous chunk's end.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ChunkBoundary:
    chunk_index: int
    start_seconds: float
    end_seconds: float
    duration_seconds: float

    def to_dict(self) -> dict[str, float | int]:
        return {
            "chunk_index": self.chunk_index,
            "start_seconds": round(self.start_seconds, 3),
            "end_seconds": round(self.end_seconds, 3),
            "duration_seconds": round(self.duration_seconds, 3),
        }


def compute_step(chunk_duration_seconds: float, chunk_overlap_seconds: float) -> float:
    """Distance between consecutive chunk starts (never <= 0)."""
    overlap = min(chunk_overlap_seconds, chunk_duration_seconds / 2)
    return chunk_duration_seconds - overlap


def plan_chunks(
    audio_duration_seconds: float,
    *,
    chunk_duration_seconds: float = 3600.0,
    chunk_overlap_seconds: float = 60.0,
) -> list[ChunkBoundary]:
    """Compute overlapping chunk boundaries for the whole audio duration.

    Example (duration 7140 s, 3600 s chunks, 60 s overlap)::

        chunk 0:    0 - 3600
        chunk 1: 3540 - 7140

    The final chunk may be shorter than the nominal duration.
    """
    if audio_duration_seconds <= 0:
        return []

    step = compute_step(chunk_duration_seconds, chunk_overlap_seconds)
    boundaries: list[ChunkBoundary] = []
    index = 0
    start = 0.0
    last_end = 0.0
    while start < audio_duration_seconds:
        end = min(start + chunk_duration_seconds, audio_duration_seconds)
        if end - start <= 0:
            break
        # A trailing chunk that ends inside the previous chunk's range would be a
        # 100% duplicate of content already analysed: skip it instead of paying
        # for an extra Gemini request.
        if end <= last_end + 0.001 and boundaries:
            index += 1
            start = index * step
            continue
        boundaries.append(
            ChunkBoundary(
                chunk_index=index,
                start_seconds=start,
                end_seconds=end,
                duration_seconds=end - start,
            )
        )
        last_end = end
        index += 1
        start = index * step
    # Chunk indices must stay contiguous because they are part of the unique
    # (job_id, chunk_index) database constraint and the deterministic filenames.
    return [
        ChunkBoundary(
            chunk_index=position,
            start_seconds=boundary.start_seconds,
            end_seconds=boundary.end_seconds,
            duration_seconds=boundary.duration_seconds,
        )
        for position, boundary in enumerate(boundaries)
    ]


def estimate_audio_tokens(duration_seconds: float, *, tokens_per_second: float = 32.0) -> int:
    """Estimate audio input tokens (planning only - never a billing claim)."""
    return round(max(0.0, duration_seconds) * tokens_per_second)


def refine_chunks_for_token_budget(
    boundaries: list[ChunkBoundary],
    *,
    chunk_overlap_seconds: float,
    max_safe_input_tokens: int,
    tokens_per_second: float,
    fixed_overhead_tokens: int = 2000,
) -> list[ChunkBoundary]:
    """Split any chunk whose estimated request cost exceeds the safe budget.

    The nominal 60-minute chunk is the default maximum, not a guarantee: if a
    model configuration costs more tokens, chunks are split adaptively (quality
    beats minimising chunk count).
    """
    safe_duration = max(
        60.0,
        (max_safe_input_tokens - fixed_overhead_tokens) / max(tokens_per_second, 0.001),
    )
    if safe_duration >= max((chunk.duration_seconds for chunk in boundaries), default=0.0):
        return boundaries

    refined: list[ChunkBoundary] = []
    index = 0
    for chunk in boundaries:
        if chunk.duration_seconds <= safe_duration:
            refined.append(
                ChunkBoundary(
                    chunk_index=index,
                    start_seconds=chunk.start_seconds,
                    end_seconds=chunk.end_seconds,
                    duration_seconds=chunk.duration_seconds,
                )
            )
            index += 1
            continue

        logger.warning(
            "chunk_split_for_token_budget chunk=%s duration=%.0f safe=%.0f",
            chunk.chunk_index,
            chunk.duration_seconds,
            safe_duration,
        )
        sub_boundaries = plan_chunks(
            chunk.duration_seconds,
            chunk_duration_seconds=safe_duration,
            chunk_overlap_seconds=min(chunk_overlap_seconds, safe_duration / 2),
        )
        for sub in sub_boundaries:
            refined.append(
                ChunkBoundary(
                    chunk_index=index,
                    start_seconds=chunk.start_seconds + sub.start_seconds,
                    end_seconds=min(chunk.start_seconds + sub.end_seconds, chunk.end_seconds),
                    duration_seconds=sub.duration_seconds,
                )
            )
            index += 1
    return refined


def count_chunks(duration_seconds: float, *, chunk_duration: float, overlap: float) -> int:
    """Chunk count used by the preflight estimate (same rule as plan_chunks)."""
    return len(
        plan_chunks(
            duration_seconds,
            chunk_duration_seconds=chunk_duration,
            chunk_overlap_seconds=overlap,
        )
    )
