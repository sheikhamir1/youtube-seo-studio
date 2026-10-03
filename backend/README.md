# Backend - YouTube SEO Studio

FastAPI application that contains the API layer, the persistent worker subsystem
and the FFmpeg media pipeline.

```
app/
├── main.py              # FastAPI app, lifespan: settings -> db -> seed -> worker
├── cli.py               # optional maintenance CLI (seed/status/cleanup/orphans)
├── api/v1/              # thin routers: health, system, uploads, jobs, results, prompt-templates
├── core/                # config, enums, errors, logging, security, time utils, constants
├── db/                  # declarative base, async engine/session, FastAPI dependency
├── models/              # SQLAlchemy 2.x models (UUID PKs, JSONB, UTC timestamps)
├── schemas/             # Pydantic v2 request/response models
├── repositories/        # database access only (no FFmpeg, no Gemini, no HTTP)
├── services/            # business logic
│   ├── uploads/         # resumable upload session + streaming part writer
│   ├── media/           # FFprobe, FFmpeg extraction, chunking math
│   ├── ai/              # Gemini client adapter, mock client, rate limiter, map, reduce
│   ├── jobs/            # state machine, progress model, orchestrator
│   ├── prompts/         # immutable prompts, sandboxed template rendering
│   ├── timeline/        # timestamp normalization + overlap deduplication
│   └── seo/             # chapter parsing/repair, SEO validation
└── worker/              # persistent worker loop, dispatcher, recovery
```

## Quick start (native development)

```bash
docker compose -f ../docker-compose.yml up -d postgres   # PostgreSQL only
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
python -m app.cli seed
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

## Tests

```bash
pytest                 # unit tests (no database/FFmpeg/API key required)
pytest tests/integration   # requires PostgreSQL
pytest tests/e2e           # requires PostgreSQL + FFmpeg (uses AI_PROVIDER=mock)
ruff check app tests && ruff format --check app tests
```

Files named `*_test.py` are not used; the suite lives in `tests/unit`,
`tests/integration` and `tests/e2e`.
