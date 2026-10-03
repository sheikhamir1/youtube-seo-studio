"""Structured logging helpers.

Every meaningful log record carries job_id / stage / chunk_index when known so
long-running jobs stay attributable. API keys and prompt bodies are never
logged.
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from typing import Any

_log_context: ContextVar[dict[str, Any] | None] = ContextVar("log_context", default=None)

SENSITIVE_KEYS = {"api_key", "gemini_api_key", "authorization", "password", "database_url"}


def set_log_context(**kwargs: Any) -> None:
    """Attach contextual fields (job_id, stage, chunk_index...) to log records."""
    current = dict(_log_context.get() or {})
    current.update({k: v for k, v in kwargs.items() if v is not None})
    _log_context.set(current)


def clear_log_context() -> None:
    # Never store a mutable default in a ContextVar: reset to None instead.
    _log_context.set(None)


def _sanitize(extra: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in extra.items() if k.lower() not in SENSITIVE_KEYS}


class ContextFilter(logging.Filter):
    """Injects the current context fields into every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        for key, value in _sanitize(dict(_log_context.get() or {})).items():
            if not hasattr(record, key):
                setattr(record, key, value)
        return True


class JsonFormatter(logging.Formatter):
    """Compact JSON logs: easy to grep while debugging long jobs."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("job_id", "stage", "chunk_index", "event", "model", "worker_id"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class ConsoleFormatter(logging.Formatter):
    """Human-friendly development formatter."""

    def format(self, record: logging.LogRecord) -> str:
        base = f"{self.formatTime(record, '%H:%M:%S')} {record.levelname:<7} {record.name:<28} {record.getMessage()}"
        context_keys = ("job_id", "stage", "chunk_index", "event")
        context = " ".join(
            f"{key}={getattr(record, key)}" for key in context_keys if getattr(record, key, None) is not None
        )
        line = f"{base}  {context}" if context else base
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


def configure_logging(level: str = "INFO", *, json_logs: bool = False) -> None:
    """Configure the root logger once at application startup."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if json_logs else ConsoleFormatter())
    handler.addFilter(ContextFilter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())

    # These libraries are chatty at INFO level.
    for noisy in ("httpx", "httpcore", "asyncio", "sqlalchemy.engine.Engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
