"""Upload part math and file-safety helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.errors import StorageError
from app.core.security import ensure_within_directory, safe_join, sanitize_filename
from app.services.uploads.service import UploadService


def test_total_parts_ceiling_division():
    assert UploadService.total_parts_for(size_bytes=32 * 1024 * 1024, chunk_size_bytes=32 * 1024 * 1024) == 1
    assert (
        UploadService.total_parts_for(size_bytes=32 * 1024 * 1024 + 1, chunk_size_bytes=32 * 1024 * 1024) == 2
    )
    # A 20 GB file with 32 MiB parts: many parts, never one giant request.
    assert UploadService.total_parts_for(size_bytes=20 * 1024**3, chunk_size_bytes=32 * 1024**2) == 640


def test_next_missing_part_detects_gaps():
    assert UploadService.next_missing_part(total_parts=5, received_parts=[0, 1, 2, 3, 4]) is None
    assert UploadService.next_missing_part(total_parts=5, received_parts=[0, 1, 3, 4]) == 2
    assert UploadService.next_missing_part(total_parts=5, received_parts=[]) == 0


def test_sanitize_filename_strips_paths_and_metacharacters():
    # Path components are always discarded: only the base name survives.
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename("/tmp/a/b/lecture final.mp4") == "lecture final.mp4"

    hostile = "lecture; rm -rf $(whoami) && echo pwned.mp4"
    cleaned = sanitize_filename(hostile)
    assert not any(char in cleaned for char in ";$&()`|<>\\/")
    assert cleaned.endswith(".mp4")

    assert sanitize_filename("") == "video"
    assert len(sanitize_filename("x" * 400 + ".mp4")) <= 180


def test_ensure_within_directory_blocks_traversal(tmp_path: Path):
    base = tmp_path / "data"
    base.mkdir()
    inside = base / "jobs" / "abc"
    assert ensure_within_directory(inside, base) == inside.resolve()
    with pytest.raises(StorageError):
        ensure_within_directory(tmp_path / "outside", base)
    with pytest.raises(StorageError):
        ensure_within_directory(base / ".." / "escaped", base)


def test_safe_join_ignores_traversal_components(tmp_path: Path):
    base = tmp_path / "data"
    base.mkdir()
    assert safe_join(base, "..", "etc", "passwd") == (base / "etc" / "passwd").resolve()
