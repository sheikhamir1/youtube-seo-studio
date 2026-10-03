"""Initial schema: uploads, jobs, chunks, SEO results, events, AI request log.

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-24
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ----------------------------------------------------------- prompt_templates
    op.create_table(
        "prompt_templates",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("user_prompt_template", sa.Text(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_prompt_templates_name", "prompt_templates", ["name"], unique=True)
    op.create_unique_constraint("uq_prompt_templates_name", "prompt_templates", ["name"])

    # ------------------------------------------------------------ upload_sessions
    op.create_table(
        "upload_sessions",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(length=160), nullable=True),
        sa.Column("expected_size", sa.BigInteger(), nullable=False),
        sa.Column("received_size", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("chunk_size", sa.BigInteger(), nullable=False),
        sa.Column("total_parts", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="UPLOADING"),
        sa.Column("temporary_path", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_upload_sessions_status", "upload_sessions", ["status"])

    op.create_table(
        "upload_parts",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "upload_session_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("upload_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("part_number", sa.Integer(), nullable=False),
        sa.Column("byte_offset", sa.BigInteger(), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("upload_session_id", "part_number", name="uq_upload_parts_session_part"),
    )
    op.create_index("ix_upload_parts_upload_session_id", "upload_parts", ["upload_session_id"])

    # ---------------------------------------------------------------------- jobs
    op.create_table(
        "jobs",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "upload_session_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("upload_sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("source_size_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("video_duration_seconds", sa.Float(), nullable=True),
        sa.Column("audio_stream_index", sa.Integer(), nullable=True),
        sa.Column("audio_stream_language", sa.String(length=80), nullable=True),
        sa.Column(
            "audio_stream_start_offset_seconds", sa.Float(), nullable=False, server_default="0"
        ),
        sa.Column("audio_duration_seconds", sa.Float(), nullable=True),
        sa.Column("media_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="QUEUED"),
        sa.Column("stage", sa.String(length=24), nullable=False, server_default="PENDING"),
        sa.Column("progress_percent", sa.Float(), nullable=False, server_default="0"),
        sa.Column("current_chunk_index", sa.Integer(), nullable=True),
        sa.Column("total_chunks", sa.Integer(), nullable=True),
        sa.Column("selected_model", sa.String(length=120), nullable=False),
        sa.Column(
            "prompt_template_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("prompt_templates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("prompt_template_name_snapshot", sa.String(length=200), nullable=True),
        sa.Column("system_prompt_snapshot", sa.Text(), nullable=True),
        sa.Column("user_prompt_template_snapshot", sa.Text(), nullable=True),
        sa.Column("pipeline_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("seo_context", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("timeline_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("current_error_code", sa.String(length=80), nullable=True),
        sa.Column("current_error_message", sa.Text(), nullable=True),
        sa.Column("failed_stage", sa.String(length=24), nullable=True),
        sa.Column("failed_chunk_index", sa.Integer(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("worker_id", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_status_created_at", "jobs", ["status", "created_at"])
    op.create_index("ix_jobs_created_at", "jobs", ["created_at"])
    op.create_index("ix_jobs_updated_at", "jobs", ["updated_at"])
    op.create_index("ix_jobs_last_heartbeat_at", "jobs", ["last_heartbeat_at"])

    # -------------------------------------------------------------- audio_chunks
    op.create_table(
        "audio_chunks",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("job_id", sa.Uuid(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("start_seconds", sa.Float(), nullable=False),
        sa.Column("end_seconds", sa.Float(), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("local_path", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="PENDING"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("relative_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("normalized_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("estimated_input_tokens", sa.Integer(), nullable=True),
        sa.Column("actual_input_tokens", sa.Integer(), nullable=True),
        sa.Column("actual_output_tokens", sa.Integer(), nullable=True),
        sa.Column("gemini_file_name", sa.Text(), nullable=True),
        sa.Column("gemini_file_uri", sa.Text(), nullable=True),
        sa.Column("gemini_file_cleaned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("job_id", "chunk_index", name="uq_audio_chunks_job_id_chunk_index"),
    )
    op.create_index("ix_audio_chunks_job_id", "audio_chunks", ["job_id"])
    op.create_index("ix_audio_chunks_status", "audio_chunks", ["status"])
    op.create_index("ix_audio_chunks_job_id_status", "audio_chunks", ["job_id", "status"])

    # --------------------------------------------------------------- seo_results
    op.create_table(
        "seo_results",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("job_id", sa.Uuid(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("seo_score", sa.Integer(), nullable=False),
        sa.Column("improvement_suggestions", sa.Text(), nullable=False),
        sa.Column("thumbnail_prompt", sa.Text(), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column(
            "prompt_template_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("prompt_templates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("prompt_template_name_snapshot", sa.String(length=200), nullable=True),
        sa.Column("raw_response", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("validation_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("chapters", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("edited_by_user", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("job_id", "version_number", name="uq_seo_results_job_id_version_number"),
        sa.CheckConstraint("seo_score >= 0 AND seo_score <= 100", name="ck_seo_results_seo_score_range"),
    )
    op.create_index("ix_seo_results_job_id", "seo_results", ["job_id"])
    op.create_index("ix_seo_results_version_number", "seo_results", ["version_number"])
    op.create_index("ix_seo_results_is_current", "seo_results", ["is_current"])
    op.create_index("ix_seo_results_job_id_is_current", "seo_results", ["job_id", "is_current"])

    # ---------------------------------------------------------------- job_events
    op.create_table(
        "job_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.Uuid(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence_number", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(length=48), nullable=False),
        sa.Column("level", sa.String(length=12), nullable=False, server_default="INFO"),
        sa.Column("stage", sa.String(length=24), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("progress_percent", sa.Float(), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_job_events_job_id", "job_events", ["job_id"])
    op.create_index(
        "ix_job_events_job_id_sequence_number", "job_events", ["job_id", "sequence_number"]
    )

    # ------------------------------------------------------------ ai_request_logs
    op.create_table(
        "ai_request_logs",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("job_id", sa.Uuid(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=True),
        sa.Column(
            "audio_chunk_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("audio_chunks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("phase", sa.String(length=24), nullable=False, server_default="MAP"),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("estimated_input_tokens", sa.Integer(), nullable=True),
        sa.Column("actual_input_tokens", sa.Integer(), nullable=True),
        sa.Column("actual_output_tokens", sa.Integer(), nullable=True),
        sa.Column("actual_total_tokens", sa.Integer(), nullable=True),
        sa.Column("thinking_tokens", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
        sa.Column("http_status_code", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ai_request_logs_started_at", "ai_request_logs", ["started_at"])
    op.create_index("ix_ai_request_logs_job_id", "ai_request_logs", ["job_id"])
    op.create_index("ix_ai_request_logs_phase", "ai_request_logs", ["phase"])
    op.create_index(
        "ix_ai_request_logs_status_started_at", "ai_request_logs", ["status", "started_at"]
    )

    # -------------------------------------------------------------- app_settings
    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("default_model", sa.String(length=120), nullable=False),
        sa.Column(
            "allowed_models", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"
        ),
        sa.Column("gemini_rpm_limit", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("gemini_tpm_limit", sa.Integer(), nullable=False, server_default="250000"),
        sa.Column("gemini_rpd_limit", sa.Integer(), nullable=False, server_default="500"),
        sa.Column("gemini_min_interval_seconds", sa.Float(), nullable=False, server_default="60"),
        sa.Column("chunk_duration_seconds", sa.Float(), nullable=False, server_default="3600"),
        sa.Column("chunk_overlap_seconds", sa.Float(), nullable=False, server_default="60"),
        sa.Column("map_max_topics_per_chunk", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("max_gemini_retries", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("max_schema_repair_attempts", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("audio_format", sa.String(length=12), nullable=False, server_default="flac"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ------------------------------------------------------------- worker_states
    op.create_table(
        "worker_states",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("worker_id", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="STARTING"),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "current_job_id", sa.Uuid(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("current_stage", sa.String(length=24), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("worker_id", name="uq_worker_states_worker_id"),
    )
    op.create_index("ix_worker_states_worker_id", "worker_states", ["worker_id"], unique=True)


def downgrade() -> None:
    op.drop_table("worker_states")
    op.drop_table("app_settings")
    op.drop_table("ai_request_logs")
    op.drop_table("job_events")
    op.drop_table("seo_results")
    op.drop_table("audio_chunks")
    op.drop_table("jobs")
    op.drop_table("upload_parts")
    op.drop_table("upload_sessions")
    op.drop_table("prompt_templates")
