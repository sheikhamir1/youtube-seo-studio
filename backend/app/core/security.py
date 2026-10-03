"""Filesystem and input safety helpers.

Even though this application is local and single-user, user-supplied filenames
must never reach a shell or escape the configured data directory.
"""

from __future__ import annotations

import os
import re
import shutil
import unicodedata
from pathlib import Path

from app.core.errors import StorageError, ValidationError

_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._ \-]+")
_SHELL_METACHARACTERS = re.compile(r"[;&|`$><\n\r\t\\\"'*?!#]")


def sanitize_filename(filename: str, *, max_length: int = 180) -> str:
    """Return a display-safe filename (never used as a filesystem path)."""
    name = Path(filename or "").name.strip()
    name = unicodedata.normalize("NFC", name)
    name = _UNSAFE_FILENAME_CHARS.sub("_", name)
    name = name.strip(" .")
    if not name:
        name = "video"
    if len(name) > max_length:
        stem, dot, suffix = name.rpartition(".")
        if dot and len(suffix) <= 12:
            name = stem[: max_length - len(suffix) - 1] + "." + suffix
        else:
            name = name[:max_length]
    return name


def assert_no_shell_metacharacters(value: str, *, field: str = "value") -> str:
    """Defence-in-depth check; FFmpeg is invoked without a shell anyway."""
    if _SHELL_METACHARACTERS.search(value):
        raise ValidationError(f"{field} contains characters that are not allowed.", details=value)
    return value


def ensure_within_directory(path: Path, directory: Path) -> Path:
    """Resolve ``path`` and guarantee it stays inside ``directory``."""
    resolved = path.expanduser().resolve()
    base = directory.expanduser().resolve()
    if resolved != base and base not in resolved.parents:
        raise StorageError(
            "Refusing to operate on a path outside the configured data directory.",
            details={"path": str(resolved), "data_dir": str(base)},
        )
    return resolved


def safe_join(directory: Path, *parts: str) -> Path:
    """Join untrusted components onto ``directory`` and validate the result."""
    candidate = directory.joinpath(*[p for p in parts if p not in ("", ".", "..")])
    return ensure_within_directory(candidate, directory)


def assert_disk_space(path: Path, required_bytes: int) -> None:
    """Raise a clear error before writing when the disk is (nearly) full."""
    path.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(path)
    available = usage.free
    if available < required_bytes:
        from app.core.errors import DiskFullError

        raise DiskFullError(
            details={
                "available_bytes": available,
                "required_bytes": required_bytes,
                "path": str(path),
            }
        )


def disk_usage(path: Path) -> dict[str, float]:
    """Return basic disk information used by the system status API."""
    target = path if path.exists() else Path()
    usage = shutil.disk_usage(target)
    total = usage.total
    free = usage.free
    used = usage.used
    return {
        "path": str(target),
        "total_bytes": float(total),
        "used_bytes": float(used),
        "free_bytes": float(free),
        "used_percent": round((used / total) * 100, 2) if total else 0.0,
    }
