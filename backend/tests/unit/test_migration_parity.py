"""Model <-> Alembic migration parity.

The migration is the source of truth for a real PostgreSQL database, while the
models are the source of truth for the ORM. Any drift between them produces a
broken deployment that no other fast test would catch, so this test replays the
migration's ``upgrade()`` against a recording ``alembic.op`` and compares the
resulting schema with ``Base.metadata``.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app import models  # noqa: F401  (registers every table)
from app.db.base import Base

MIGRATION_PATH = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "0001_initial_schema.py"


class RecordingOp:
    """Minimal stand-in for ``alembic.op`` that records DDL operations."""

    def __init__(self) -> None:
        self.tables: dict[str, dict[str, Any]] = {}
        self.indexes: list[tuple[str, str]] = []
        self.unique_constraints: list[tuple[str, str]] = []

    def create_table(self, name: str, *columns: Any, **kwargs: Any) -> None:
        """Build a real Table so constraints/columns resolve exactly as in DDL."""
        metadata = sa.MetaData()
        table = sa.Table(name, metadata, *columns, **kwargs)
        self.tables[name] = {
            "columns": {column.name: column for column in table.columns},
            "table": table,
            "kwargs": kwargs,
        }

    def create_index(self, index_name: str, table_name: str, columns: Any, **kwargs: Any) -> None:
        self.indexes.append((table_name, index_name))

    def create_unique_constraint(self, name: str, table: str, columns: Any, **kwargs: Any) -> None:
        self.unique_constraints.append((table, name))

    def drop_table(self, name: str, **kwargs: Any) -> None:
        self.tables.pop(name, None)

    def __getattr__(self, item: str):  # pragma: no cover - unexpected DDL is reported
        def _unsupported(*args: Any, **kwargs: Any) -> None:
            raise AssertionError(f"unsupported migration operation: {item}")

        return _unsupported


@pytest.fixture(scope="module")
def recorded_schema() -> RecordingOp:
    """Import the migration module and replay ``upgrade()`` against a recorder."""
    spec = importlib.util.spec_from_file_location("migration_0001", MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    recorder = RecordingOp()
    original_op = module.op
    module.op = recorder
    try:
        module.upgrade()
    finally:
        module.op = original_op
    return recorder


def test_same_tables_are_created(recorded_schema: RecordingOp):
    metadata_tables = set(Base.metadata.tables)
    migration_tables = set(recorded_schema.tables)
    assert metadata_tables == migration_tables, (
        f"missing in migration: {metadata_tables - migration_tables}; "
        f"extra in migration: {migration_tables - metadata_tables}"
    )


@pytest.mark.parametrize("table_name", sorted(Base.metadata.tables))
def test_columns_match(table_name: str, recorded_schema: RecordingOp):
    model_columns = {column.name for column in Base.metadata.tables[table_name].columns}
    migration_columns = set(recorded_schema.tables[table_name]["columns"])
    assert model_columns == migration_columns, (
        f"{table_name}: missing in migration: {model_columns - migration_columns}; "
        f"extra in migration: {migration_columns - model_columns}"
    )


@pytest.mark.parametrize("table_name", sorted(Base.metadata.tables))
def test_nullability_matches(table_name: str, recorded_schema: RecordingOp):
    model_table = Base.metadata.tables[table_name]
    migration_columns = recorded_schema.tables[table_name]["columns"]
    mismatches = []
    for column in model_table.columns:
        migration_column = migration_columns[column.name]
        model_nullable = bool(column.nullable)
        migration_nullable = bool(migration_column.nullable)
        # Columns with a server default may be declared NOT NULL in the model.
        if model_nullable != migration_nullable and migration_column.server_default is None:
            mismatches.append(
                f"{column.name}: model nullable={model_nullable}, migration nullable={migration_nullable}"
            )
    assert not mismatches, f"{table_name} nullability drift: {mismatches}"


@pytest.mark.parametrize("table_name", sorted(Base.metadata.tables))
def test_primary_keys_match(table_name: str, recorded_schema: RecordingOp):
    model_pk = {column.name for column in Base.metadata.tables[table_name].primary_key.columns}
    migration_columns = recorded_schema.tables[table_name]["columns"]
    migration_pk = {name for name, column in migration_columns.items() if bool(column.primary_key)}
    assert model_pk == migration_pk, f"{table_name} primary key drift"


@pytest.mark.parametrize("table_name", sorted(Base.metadata.tables))
def test_foreign_keys_match(table_name: str, recorded_schema: RecordingOp):
    model_fks = {
        fk.parent.name
        for fk in Base.metadata.tables[table_name].foreign_key_constraints
        for fk in fk.elements
    }
    migration_table: sa.Table = recorded_schema.tables[table_name]["table"]
    migration_fks = {
        element.parent.name
        for constraint in migration_table.foreign_key_constraints
        for element in constraint.elements
    }
    assert (
        model_fks == migration_fks
    ), f"{table_name}: missing in migration: {model_fks - migration_fks}; extra: {migration_fks - model_fks}"


@pytest.mark.parametrize("table_name", sorted(Base.metadata.tables))
def test_unique_constraints_match(table_name: str, recorded_schema: RecordingOp):
    model_unique = {
        tuple(sorted(constraint.columns.keys()))
        for constraint in Base.metadata.tables[table_name].constraints
        if isinstance(constraint, sa.UniqueConstraint)
    }
    entry = recorded_schema.tables[table_name]
    migration_table: sa.Table = entry["table"]
    migration_unique = {
        tuple(sorted(constraint.columns.keys()))
        for constraint in migration_table.constraints
        if isinstance(constraint, sa.UniqueConstraint)
    }
    migration_unique |= {(column_name,) for column_name, column in entry["columns"].items() if column.unique}
    assert (
        model_unique <= migration_unique
    ), f"{table_name}: unique constraints missing from the migration: {model_unique - migration_unique}"


def test_expected_indexes_exist(recorded_schema: RecordingOp):
    """Indexes required by the specification's hot query paths."""
    expected = {
        ("jobs", "ix_jobs_status"),
        ("jobs", "ix_jobs_status_created_at"),
        ("jobs", "ix_jobs_created_at"),
        ("jobs", "ix_jobs_updated_at"),
        ("jobs", "ix_jobs_last_heartbeat_at"),
        ("audio_chunks", "ix_audio_chunks_job_id"),
        ("audio_chunks", "ix_audio_chunks_status"),
        ("audio_chunks", "ix_audio_chunks_job_id_status"),
        ("seo_results", "ix_seo_results_job_id"),
        ("seo_results", "ix_seo_results_version_number"),
        ("seo_results", "ix_seo_results_is_current"),
        ("job_events", "ix_job_events_job_id_sequence_number"),
        ("ai_request_logs", "ix_ai_request_logs_started_at"),
        ("ai_request_logs", "ix_ai_request_logs_job_id"),
        ("ai_request_logs", "ix_ai_request_logs_phase"),
    }
    assert expected <= set(recorded_schema.indexes)


def test_seo_score_check_constraint_is_declared(recorded_schema: RecordingOp):
    # Declared on the ORM model...
    table = Base.metadata.tables["seo_results"]
    checks = [
        str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, sa.CheckConstraint)
    ]
    assert any("seo_score" in text for text in checks), "seo_score must be constrained to 0..100"

    # ...and also present in the migration actually applied to PostgreSQL.
    migration_table: sa.Table = recorded_schema.tables["seo_results"]["table"]
    migration_checks = [
        str(constraint.sqltext)
        for constraint in migration_table.constraints
        if isinstance(constraint, sa.CheckConstraint)
    ]
    assert any(
        "seo_score" in text for text in migration_checks
    ), "the migration must create the seo_score range constraint"


def test_timestamps_are_timezone_aware():
    """All timestamps are UTC: never a naive DateTime column."""
    naive: list[str] = []
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, sa.DateTime) and not column.type.timezone:
                naive.append(f"{table.name}.{column.name}")
    assert not naive, f"naive (timezone-less) timestamps found: {naive}"


def test_json_columns_use_jsonb():
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, postgresql.JSONB):
                continue
            if isinstance(column.type, sa.JSON) and not isinstance(column.type, postgresql.JSONB):
                raise AssertionError(f"{table.name}.{column.name} should use JSONB, not JSON")


def test_uuid_primary_keys_everywhere():
    for name, table in Base.metadata.tables.items():
        if name in {"job_events", "app_settings"}:
            continue  # BIGSERIAL for the event stream, integer singleton for settings
        pk_columns = list(table.primary_key.columns)
        assert len(pk_columns) == 1, f"{name} should have a single primary key"
        assert isinstance(pk_columns[0].type, sa.Uuid), f"{name} primary key should be a UUID"
