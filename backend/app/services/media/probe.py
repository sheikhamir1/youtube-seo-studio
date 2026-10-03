"""MediaProbeService: FFprobe metadata, stream selection and validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.errors import ErrorCode, MediaError
from app.core.logging import get_logger
from app.services.media.ffmpeg_runner import run_ffprobe

logger = get_logger(__name__)

# Containers/codecs that are commonly incompatible with a direct audio decode
# are still accepted: FFmpeg decodes whatever it can and reports failure clearly.
UNSUPPORTED_AUDIO_CODECS = {"none"}


@dataclass
class AudioStreamInfo:
    index: int
    codec: str | None
    sample_rate: int | None
    channels: int | None
    channel_layout: str | None
    language: str | None
    is_default: bool
    start_time_seconds: float
    duration_seconds: float | None
    title: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "codec": self.codec,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "channel_layout": self.channel_layout,
            "language": self.language,
            "is_default": self.is_default,
            "start_time_seconds": self.start_time_seconds,
            "duration_seconds": self.duration_seconds,
            "title": self.title,
        }


@dataclass
class MediaInfo:
    path: str
    duration_seconds: float
    format_name: str | None
    format_long_name: str | None
    size_bytes: int | None
    bit_rate: int | None
    video_codec: str | None
    width: int | None
    height: int | None
    frame_rate: float | None
    has_video: bool
    audio_streams: list[AudioStreamInfo]
    selected_audio_stream: AudioStreamInfo

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "duration_seconds": self.duration_seconds,
            "format_name": self.format_name,
            "format_long_name": self.format_long_name,
            "size_bytes": self.size_bytes,
            "bit_rate": self.bit_rate,
            "video_codec": self.video_codec,
            "width": self.width,
            "height": self.height,
            "frame_rate": self.frame_rate,
            "has_video": self.has_video,
            "audio_stream_index": self.selected_audio_stream.index,
            "audio_stream_language": self.selected_audio_stream.language,
            "audio_stream_start_offset_seconds": self.selected_audio_stream.start_time_seconds,
            "audio_stream_duration_seconds": self.selected_audio_stream.duration_seconds,
            "sample_rate": self.selected_audio_stream.sample_rate,
            "channels": self.selected_audio_stream.channels,
            "audio_streams": [stream.to_dict() for stream in self.audio_streams],
        }


class MediaProbeService:
    """Wraps ffprobe with the validation rules of the product.

    Note: duration is never capped at 12 hours - long videos are the point.
    """

    async def probe(self, path: Path) -> MediaInfo:
        if not path.exists():
            raise MediaError(
                "The media file could not be found on disk.",
                code=ErrorCode.MEDIA_NOT_FOUND,
                http_status=404,
            )

        payload = await run_ffprobe(
            [
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(path),
            ]
        )

        streams = payload.get("streams") or []
        format_info = payload.get("format") or {}

        if not streams:
            raise MediaError(
                "The file does not contain any readable media streams.",
                details={"code": ErrorCode.MEDIA_INVALID},
                code=ErrorCode.MEDIA_INVALID,
            )

        video_streams = [s for s in streams if s.get("codec_type") == "video"]
        audio_streams_raw = [s for s in streams if s.get("codec_type") == "audio"]

        if not audio_streams_raw:
            raise MediaError(
                "The selected video does not contain a usable audio stream.",
                code=ErrorCode.MEDIA_NO_AUDIO,
            )

        audio_streams = [self._parse_audio_stream(stream) for stream in audio_streams_raw]
        selected = self._select_audio_stream(audio_streams)

        duration = self._resolve_duration(format_info, streams)
        if duration is None:
            raise MediaError(
                "The media duration could not be determined, so chunk timestamps cannot be built.",
                code=ErrorCode.MEDIA_DURATION_UNAVAILABLE,
            )

        video_stream = video_streams[0] if video_streams else {}
        info = MediaInfo(
            path=str(path),
            duration_seconds=float(duration),
            format_name=format_info.get("format_name"),
            format_long_name=format_info.get("format_long_name"),
            size_bytes=_to_int(format_info.get("size")) or path.stat().st_size,
            bit_rate=_to_int(format_info.get("bit_rate")),
            video_codec=video_stream.get("codec_name"),
            width=_to_int(video_stream.get("width")),
            height=_to_int(video_stream.get("height")),
            frame_rate=_parse_frame_rate(video_stream.get("avg_frame_rate")),
            has_video=bool(video_streams),
            audio_streams=audio_streams,
            selected_audio_stream=selected,
        )
        logger.info(
            "media_probed duration=%.1fs audio_stream=%s offset=%.2fs video=%s",
            info.duration_seconds,
            selected.index,
            selected.start_time_seconds,
            info.video_codec,
        )
        return info

    # -------------------------------------------------------------- internals
    def _parse_audio_stream(self, stream: dict[str, Any]) -> AudioStreamInfo:
        tags = stream.get("tags") or {}
        disposition = stream.get("disposition") or {}
        start_time = _to_float(stream.get("start_time")) or 0.0
        timeout_value = _to_float(stream.get("duration"))
        return AudioStreamInfo(
            index=int(stream.get("index", 0)),
            codec=stream.get("codec_name"),
            sample_rate=_to_int(stream.get("sample_rate")),
            channels=_to_int(stream.get("channels")),
            channel_layout=stream.get("channel_layout"),
            language=tags.get("language"),
            is_default=bool(disposition.get("default", 0)),
            # Audio may legitimately start after 0 (container priming delays).
            start_time_seconds=start_time,
            duration_seconds=timeout_value,
            title=tags.get("title"),
        )

    def _select_audio_stream(self, streams: list[AudioStreamInfo]) -> AudioStreamInfo:
        """Prefer the default stream, otherwise the first compatible one."""
        for stream in streams:
            if stream.is_default and (stream.codec or "") not in UNSUPPORTED_AUDIO_CODECS:
                return stream
        for stream in streams:
            if (stream.codec or "") not in UNSUPPORTED_AUDIO_CODECS:
                return stream
        return streams[0]

    def _resolve_duration(self, format_info: dict[str, Any], streams: list[dict[str, Any]]) -> float | None:
        duration = _to_float(format_info.get("duration"))
        if duration and duration > 0:
            return duration
        candidates = [_to_float(stream.get("duration")) for stream in streams]
        candidates = [value for value in candidates if value and value > 0]
        return max(candidates) if candidates else None


def _to_int(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if result != result:  # NaN
        return None
    return result


def _parse_frame_rate(value: Any) -> float | None:
    if not value or value == "0/0":
        return None
    if isinstance(value, str) and "/" in value:
        numerator, _, denominator = value.partition("/")
        try:
            denom = float(denominator)
            return round(float(numerator) / denom, 3) if denom else None
        except ValueError:
            return None
    return _to_float(value)
