"""TimelineNormalizer: raw chunk Map results -> one coherent video timeline."""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.services.timeline.dedup import merge_topics, topics_are_duplicates

logger = get_logger(__name__)


class TimelineNormalizer:
    """Converts chunk-relative topics into absolute video timestamps.

    Offset math (this is the critical part of the whole pipeline)::

        absolute_start = audio_stream_start_offset + chunk_start + relative_start

    The audio stream offset is not assumed to be zero: some containers start the
    audio track slightly after the video, and ignoring that would shift every
    chapter. See spec sections 35 and 49.
    """

    def __init__(
        self,
        *,
        similarity_threshold: float = 0.88,
        proximity_seconds: float = 90.0,
        video_duration_seconds: float | None = None,
    ) -> None:
        self.similarity_threshold = similarity_threshold
        self.proximity_seconds = proximity_seconds
        self.video_duration_seconds = video_duration_seconds

    # ------------------------------------------------------------ public API
    def normalize(self, chunk_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Build the normalized timeline from completed chunk results.

        ``chunk_results`` items must contain ``chunk_index``, ``start_seconds``
        (chunk start on the extracted audio timeline), ``audio_start_offset`` and
        ``topics`` (relative to the chunk).
        """
        collected: list[dict[str, Any]] = []

        for chunk in chunk_results:
            chunk_index = int(chunk["chunk_index"])
            chunk_start = float(chunk.get("start_seconds", 0.0))
            audio_offset = float(chunk.get("audio_start_offset", 0.0))
            chunk_duration = float(chunk.get("duration_seconds", 0.0))

            for topic in chunk.get("topics", []) or []:
                converted = self._to_absolute(
                    topic=topic,
                    chunk_index=chunk_index,
                    chunk_start=chunk_start,
                    audio_offset=audio_offset,
                    chunk_duration=chunk_duration,
                )
                if converted is not None:
                    collected.append(converted)

        collected = self._drop_invalid(collected)
        collected.sort(key=lambda item: (item["start_seconds"], item["end_seconds"], item["topic"]))
        merged = self._deduplicate(collected)
        logger.info("timeline_normalized raw=%s merged=%s", len(collected), len(merged))
        return merged

    # -------------------------------------------------------------- internals
    def _to_absolute(
        self,
        *,
        topic: dict[str, Any],
        chunk_index: int,
        chunk_start: float,
        audio_offset: float,
        chunk_duration: float,
    ) -> dict[str, Any] | None:
        try:
            relative_start = float(topic.get("start_seconds"))
            relative_end = float(topic.get("end_seconds"))
        except (TypeError, ValueError):
            return None

        # Gemini timestamps are relative to this chunk.
        # Add the chunk's start plus the original audio stream offset
        # to convert them into video-relative absolute timestamps.
        absolute_start = audio_offset + chunk_start + relative_start
        absolute_end = audio_offset + chunk_start + relative_end

        if absolute_end <= absolute_start:
            return None
        if chunk_duration and relative_end > chunk_duration + 2.0:
            return None

        return {
            "topic": str(topic.get("topic", "")).strip(),
            "summary": str(topic.get("summary", "")).strip(),
            "start_seconds": round(absolute_start, 3),
            "end_seconds": round(absolute_end, 3),
            "source_chunk_indices": [chunk_index],
        }

    def _drop_invalid(self, topics: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Remove impossible records - never invent replacement timestamps."""
        valid: list[dict[str, Any]] = []
        for topic in topics:
            if not topic["topic"] or not topic["summary"]:
                continue
            if topic["start_seconds"] < 0:
                continue
            if topic["end_seconds"] <= topic["start_seconds"]:
                continue
            if self.video_duration_seconds and topic["start_seconds"] > self.video_duration_seconds:
                continue
            if self.video_duration_seconds:
                topic["end_seconds"] = min(topic["end_seconds"], self.video_duration_seconds)
            valid.append(topic)
        return valid

    def _deduplicate(self, topics: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Merge duplicate overlap entries without merging distinct neighbours."""
        merged: list[dict[str, Any]] = []
        for topic in topics:
            if not merged:
                merged.append(topic)
                continue
            previous = merged[-1]
            is_duplicate, score = topics_are_duplicates(
                previous,
                topic,
                threshold=self.similarity_threshold,
                proximity_seconds=self.proximity_seconds,
            )
            if is_duplicate:
                logger.debug("timeline_duplicate_merged score=%.3f topic=%s", score, topic["topic"][:60])
                merged[-1] = merge_topics(previous, topic)
            else:
                merged.append(topic)

        # A second pass catches chains (A~B, B~C) after the first merge changed shapes.
        changed = True
        while changed:
            changed = False
            compacted: list[dict[str, Any]] = []
            for topic in merged:
                if compacted:
                    previous = compacted[-1]
                    is_duplicate, _ = topics_are_duplicates(
                        previous,
                        topic,
                        threshold=self.similarity_threshold,
                        proximity_seconds=self.proximity_seconds,
                    )
                    if is_duplicate:
                        compacted[-1] = merge_topics(previous, topic)
                        changed = True
                        continue
                compacted.append(topic)
            merged = compacted
        return merged
