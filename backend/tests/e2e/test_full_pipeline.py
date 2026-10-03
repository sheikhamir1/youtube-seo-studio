"""End-to-end acceptance test with a real (synthetic) media file.

Requires FFmpeg and PostgreSQL. It runs the real pipeline - FFprobe validation,
FFmpeg audio extraction, chunking, the Map/Reduce chain - using the deterministic
``AI_PROVIDER=mock`` client, so it never consumes Gemini quota.

    docker compose up -d postgres && alembic upgrade head
    AI_PROVIDER=mock pytest tests/e2e -v
"""

from __future__ import annotations

import subprocess
from itertools import pairwise
from pathlib import Path

import pytest
import pytest_asyncio

from app.core.enums import JobStage, JobStatus
from app.db.session import session_scope
from app.repositories.events import JobEventRepository
from app.repositories.jobs import JobRepository
from app.repositories.prompt_templates import PromptTemplateRepository
from app.repositories.results import SEOResultRepository
from app.services.ai.mock_client import MockGeminiClient
from app.services.ai.rate_limiter import GeminiRateLimiter
from app.services.jobs.orchestrator import JobOrchestrator
from app.services.storage import StorageService
from tests.conftest import ffmpeg_available, postgres_available
from tests.fakes import FakeClock, FakeHistory

pytestmark = [pytest.mark.e2e, pytest.mark.integration]


@pytest.fixture(scope="module")
def synthetic_video(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Generate a short synthetic video locally - never commit media to git."""
    if not ffmpeg_available():
        pytest.skip("FFmpeg is not installed: cannot generate the test media fixture.")
    directory = tmp_path_factory.mktemp("media")
    target = directory / "synthetic lecture.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=320x240:rate=15:duration=150",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=150",
            "-shortest",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-c:a",
            "aac",
            str(target),
        ],
        check=True,
        capture_output=True,
    )
    return target


@pytest_asyncio.fixture
async def prepared_job(synthetic_video: Path, tmp_path: Path):
    """Create a real job row pointing at the synthetic media file."""
    if not postgres_available():
        pytest.skip("PostgreSQL is not reachable: start it with `docker compose up -d postgres`.")

    storage = StorageService()
    async with session_scope() as session:
        template = await PromptTemplateRepository(session).get_default()
        if template is None:
            pytest.skip("No prompt template found: run `python -m app.cli seed`.")

        job = await JobRepository(session).create(
            original_filename=synthetic_video.name,
            source_path=str(synthetic_video),
            source_size_bytes=synthetic_video.stat().st_size,
            status=JobStatus.QUEUED.value,
            stage=JobStage.PENDING.value,
            progress_percent=0.0,
            selected_model="gemini-3.5-flash",
            prompt_template_id=template.id,
            prompt_template_name_snapshot=template.name,
            system_prompt_snapshot=template.system_prompt,
            user_prompt_template_snapshot=template.user_prompt_template,
            pipeline_config={
                "chunk_duration_seconds": 60,
                "chunk_overlap_seconds": 10,
                "audio_format": "flac",
                "gemini_min_interval_seconds": 0,
                "model": "gemini-3.5-flash",
                "language": "auto",
            },
            seo_context={"video_title": "Synthetic Lecture", "content_language": "auto"},
            cancel_requested=False,
        )
        await JobEventRepository(session).append(
            job_id=job.id,
            event_type="JOB_CREATED",
            message="E2E acceptance job created",
            stage=JobStage.PENDING.value,
        )
        await session.refresh(job)
        job_id = job.id

    yield job_id

    # Cleanup: remove the generated files and the job row.
    storage.delete_job_files(job_id)
    async with session_scope() as session:
        row = await JobRepository(session).get(job_id)
        if row is not None:
            await JobRepository(session).delete(row)


@pytest_asyncio.fixture
async def orchestrator() -> JobOrchestrator:
    clock = FakeClock()
    history = FakeHistory()
    limiter = GeminiRateLimiter(
        history=history,
        clock=clock,
        min_interval_seconds=0.0,
        rpm_limit=15,
        tpm_limit=250_000,
        rpd_limit=500,
    )
    return JobOrchestrator(client=MockGeminiClient(), limiter=limiter, storage=StorageService())


async def test_full_pipeline_small_video(orchestrator: JobOrchestrator, prepared_job):
    """upload -> validate -> extract -> chunk -> map -> timeline -> reduce -> SEO."""
    job_id = prepared_job
    result = await orchestrator.process_job(job_id)
    assert result.status == JobStatus.COMPLETED.value, result.message

    async with session_scope() as session:
        job = await JobRepository(session).get(job_id)
        assert job is not None
        assert job.status == JobStatus.COMPLETED.value
        assert job.stage == JobStage.COMPLETED.value
        assert job.progress_percent == 100.0
        assert job.video_duration_seconds and 145 < job.video_duration_seconds < 155
        assert job.total_chunks and job.total_chunks >= 2  # 150 s / (60 s - 10 s overlap)
        assert job.timeline_snapshot, "a normalized timeline must be stored"
        assert job.audio_stream_start_offset_seconds >= 0

        chunks = await _chunks(session, job_id)
        assert all(chunk.status == "COMPLETED" for chunk in chunks)
        # Overlap must exist between adjacent chunk boundaries.
        for previous, current in pairwise(chunks):
            assert current.start_seconds < previous.end_seconds

        results = await SEOResultRepository(session).list_for_job(job_id)
        assert len(results) == 1
        version = results[0]
        assert version.is_current is True
        assert version.seo_score == 84
        assert len(version.title) <= 100
        assert len(version.description) <= 5000
        assert version.validation_metadata["chapter_validation"]["valid"] is True

    # Local artefacts must exist after a successful run.
    paths = StorageService().job_paths(job_id)
    assert paths.timeline_file.exists()
    assert paths.seo_result_file(1).exists()
    assert paths.extracted_audio_file.exists()


async def test_restart_resume_does_not_repeat_completed_chunks(orchestrator: JobOrchestrator, prepared_job):
    """Acceptance test 270: a restarted worker keeps completed chunk results."""
    job_id = prepared_job
    await orchestrator.process_job(job_id)

    async with session_scope() as session:
        before = await _chunks(session, job_id)
        attempts_before = {chunk.chunk_index: chunk.attempt_count for chunk in before}

    # Simulate a backend restart: a fresh orchestrator resumes the same job.
    async with session_scope() as session:
        await JobRepository(session).update_fields(
            job_id, status=JobStatus.QUEUED.value, stage=JobStage.MAPPING.value
        )

    second = JobOrchestrator(
        client=MockGeminiClient(),
        limiter=GeminiRateLimiter(history=FakeHistory(), clock=FakeClock(), min_interval_seconds=0),
        storage=StorageService(),
    )
    result = await second.process_job(job_id)
    assert result.status == JobStatus.COMPLETED.value

    async with session_scope() as session:
        after = await _chunks(session, job_id)
        attempts_after = {chunk.chunk_index: chunk.attempt_count for chunk in after}
        results = await SEOResultRepository(session).list_for_job(job_id)

    # Completed chunks were not re-analysed.
    assert attempts_after == attempts_before
    # A second SEO version is produced, and the first version is preserved.
    assert len(results) == 2
    current = [result for result in results if result.is_current]
    assert len(current) == 1


async def test_cancellation_stops_the_pipeline(orchestrator: JobOrchestrator, prepared_job):
    """Acceptance test 185: cancel requested while running ends as CANCELED."""
    job_id = prepared_job
    async with session_scope() as session:
        await JobRepository(session).update_fields(
            job_id, cancel_requested=True, status=JobStatus.CANCEL_REQUESTED.value
        )
    result = await orchestrator.process_job(job_id)
    assert result.status == JobStatus.CANCELED.value

    async with session_scope() as session:
        job = await JobRepository(session).get(job_id)
        assert job is not None and job.status == JobStatus.CANCELED.value
        assert all(chunk.status != "PROCESSING" for chunk in await _chunks(session, job_id))


async def _chunks(session, job_id):
    from app.repositories.chunks import ChunkRepository

    return await ChunkRepository(session).list_for_job(job_id)


def test_environment_has_no_typescript() -> None:
    """The specification forbids TypeScript anywhere in the project."""
    root = Path(__file__).resolve().parents[3]
    forbidden = [
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix in {".ts", ".tsx"} and "node_modules" not in path.parts
    ]
    assert not forbidden, f"TypeScript files found: {forbidden[:5]}"


def test_no_forbidden_components_were_introduced() -> None:
    """No Redis, Celery, RabbitMQ or RAG/vector-store components were added.

    The check inspects real dependency declarations and imports - not comments -
    so the documentation can still explain that these are deliberately absent.
    """
    import json
    import re

    root = Path(__file__).resolve().parents[3]
    forbidden = (
        "redis",
        "celery",
        "rabbitmq",
        "kombu",
        "faiss",
        "pinecone",
        "qdrant",
        "weaviate",
        "pgvector",
    )
    offenders: list[str] = []

    # 1) Python / JavaScript dependency manifests.
    for manifest in list(root.glob("backend/requirements*.txt")) + list(root.glob("frontend/package.json")):
        if manifest.suffix == ".json":
            payload = json.loads(manifest.read_text())
            declared = {
                **payload.get("dependencies", {}),
                **payload.get("devDependencies", {}),
            }
            offenders.extend(
                f"{manifest.name}: {name}"
                for name in declared
                if any(term in name.lower() for term in forbidden)
            )
            continue
        for line in manifest.read_text().splitlines():
            entry = line.strip()
            if not entry or entry.startswith(("#", "-")):
                continue
            name = re.split(r"[<>=!\[]", entry)[0].strip().lower()
            if any(term in name for term in forbidden):
                offenders.append(f"{manifest.name}: {entry}")

    # 2) Docker Compose services / images.
    compose = root / "docker-compose.yml"
    if compose.exists():
        for line in compose.read_text().splitlines():
            stripped = line.split("#", 1)[0].strip()
            if not stripped:
                continue
            lowered = stripped.lower()
            if any(
                re.match(rf"^\s*{term}\s*:", lowered) or f"image: {term}" in lowered for term in forbidden
            ):
                offenders.append(f"docker-compose.yml: {stripped}")

    # 3) Real imports in application code (comments and docstrings may mention them).
    import_pattern = re.compile(r"^\s*(?:from|import)\s+([a-zA-Z0-9_\.]+)", re.MULTILINE)
    for path in list((root / "backend" / "app").rglob("*.py")) + list(
        (root / "frontend" / "src").rglob("*.js*")
    ):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in import_pattern.finditer(text):
            module = match.group(1).split(".")[0].lower()
            if module in forbidden:
                offenders.append(f"{path.name}: import {module}")

    assert not offenders, f"forbidden dependency found: {offenders}"


def test_no_vector_database_or_rag_pipeline_in_application_code() -> None:
    """The architecture is Map-Reduce over audio, explicitly not RAG."""
    root = Path(__file__).resolve().parents[3] / "backend" / "app"
    banned_markers = ("embedding_store", "vector_store", "retrieval_pipeline", "langchain")
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        offenders.extend(f"{path.name}: {marker}" for marker in banned_markers if marker in text)
    assert not offenders, f"RAG-style component detected: {offenders}"


def test_no_unfinished_placeholders_in_core_code() -> None:
    """No TODO/FIXME/NotImplementedError and no stub function bodies.

    A ``pass`` inside an ``except`` block is legitimate; a function or class whose
    entire body is ``pass`` is an unfinished feature, which the specification
    forbids in core product code.
    """
    import ast

    root = Path(__file__).resolve().parents[3] / "backend" / "app"
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for marker in ("TODO:", "FIXME:", "NotImplementedError", "coming soon", "placeholder"):
            if marker in text:
                offenders.append(f"{path.name}: {marker}")
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                continue
            body = [
                item
                for item in node.body
                if not isinstance(item, ast.Expr) or not isinstance(item.value, ast.Constant)
            ]
            if len(body) == 1 and isinstance(body[0], ast.Pass):
                offenders.append(f"{path.name}: unfinished body in {node.name}")
    assert not offenders, f"unfinished placeholders found: {offenders}"


def test_example_env_lists_every_documented_setting() -> None:
    root = Path(__file__).resolve().parents[3]
    env_example = (root / ".env.example").read_text()
    for key in (
        "DATABASE_URL",
        "GEMINI_API_KEY",
        "GEMINI_MODEL",
        "GEMINI_MIN_INTERVAL_SECONDS",
        "CHUNK_DURATION_SECONDS",
        "CHUNK_OVERLAP_SECONDS",
        "DATA_DIR",
        "CORS_ORIGINS",
    ):
        assert key in env_example, f"{key} is missing from .env.example"
