# ---------------------------------------------------------------------------
# YouTube SEO Studio - backend image (FastAPI + persistent worker + FFmpeg)
# ---------------------------------------------------------------------------
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=production-local \
    DATA_DIR=/app/data

WORKDIR /app

# FFmpeg/FFprobe are required for local audio extraction and chunking.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first so the layer is cached across code changes.
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# Application code, migrations and the entrypoint script.
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh && mkdir -p /app/data

EXPOSE 8000

# Migrations run before the server starts; a failing migration stops the
# container instead of pretending to be healthy.
ENTRYPOINT ["./docker-entrypoint.sh"]
