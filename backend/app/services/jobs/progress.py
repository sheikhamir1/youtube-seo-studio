"""Progress model: real work, weighted by stage (never a fake timer)."""

from __future__ import annotations

from app.core.constants import STAGE_WEIGHTS

# Order of stages for cumulative weighting.
_STAGE_ORDER = ("VALIDATION", "EXTRACTION", "CHUNKING", "MAPPING", "REDUCTION")


def _cumulative_before(stage: str) -> float:
    total = 0.0
    for name in _STAGE_ORDER:
        if name == stage:
            break
        total += STAGE_WEIGHTS.get(name, 0.0)
    return total


def compute_progress(
    *,
    stage: str,
    stage_fraction: float = 0.0,
    completed_chunks: int = 0,
    total_chunks: int | None = None,
) -> float:
    """Overall job progress percentage from real stage work.

    Mapping progress uses ``completed_chunks / total_chunks``; other stages use
    the fraction reported by FFmpeg/FFprobe work already done.
    """
    stage_key = (stage or "").upper()

    if stage_key in {"COMPLETED"}:
        return 100.0
    if stage_key in {"FAILED", "CANCELED", "PENDING"}:
        return 0.0
    if stage_key == "REDUCTION":
        fraction = max(0.0, min(1.0, stage_fraction))
        return round(min(100.0, _cumulative_before("REDUCTION") + STAGE_WEIGHTS["REDUCTION"] * fraction), 2)
    if stage_key == "MAPPING":
        if total_chunks:
            fraction = max(0.0, min(1.0, completed_chunks / total_chunks))
        else:
            fraction = max(0.0, min(1.0, stage_fraction))
        return round(min(100.0, _cumulative_before("MAPPING") + STAGE_WEIGHTS["MAPPING"] * fraction), 2)
    if stage_key in STAGE_WEIGHTS:
        fraction = max(0.0, min(1.0, stage_fraction))
        return round(min(100.0, _cumulative_before(stage_key) + STAGE_WEIGHTS[stage_key] * fraction), 2)
    return 0.0


def stage_weight_snapshot() -> dict[str, float]:
    return dict(STAGE_WEIGHTS)
