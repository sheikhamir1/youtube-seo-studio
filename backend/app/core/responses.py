"""API response envelope and exception handlers.

Contract::

    success -> {"data": <payload>, "message": "OK", "error": null}
    failure -> {"data": null, "message": "...", "error": {"code": "...", "details": ...}}
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import AppError, ErrorCode
from app.core.logging import get_logger

logger = get_logger(__name__)


def success(data: Any = None, message: str = "OK") -> dict[str, Any]:
    """Envelope for successful responses returned by routers."""
    return {"data": data, "message": message, "error": None}


def failure(
    code: str,
    message: str,
    *,
    details: Any = None,
    status_code: int = 400,
) -> JSONResponse:
    """Envelope for failed responses."""
    return JSONResponse(
        status_code=status_code,
        content={
            "data": None,
            "message": message,
            "error": {"code": code, "details": details},
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Attach consistent error handling to the FastAPI application."""

    @app.exception_handler(AppError)
    async def _app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        logger.warning("application_error code=%s message=%s", exc.code, exc.message)
        return failure(exc.code, exc.message, details=exc.details, status_code=exc.http_status)

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return failure(
            ErrorCode.VALIDATION_ERROR,
            "The submitted data is invalid.",
            details=exc.errors(),
            status_code=422,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {404: ErrorCode.NOT_FOUND, 405: "METHOD_NOT_ALLOWED", 409: ErrorCode.INVALID_JOB_STATE}.get(
            exc.status_code, ErrorCode.INTERNAL_ERROR
        )
        return failure(code, str(exc.detail), status_code=exc.status_code)

    @app.exception_handler(SQLAlchemyError)
    async def _db_handler(_: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.error("database_error: %s", exc.__class__.__name__, exc_info=True)
        return failure(
            ErrorCode.DATABASE_UNAVAILABLE,
            "The database request failed. Check that PostgreSQL is running.",
            details=exc.__class__.__name__,
            status_code=503,
        )

    @app.exception_handler(Exception)
    async def _unhandled_handler(_: Request, exc: Exception) -> JSONResponse:
        # Never expose Python stack traces to the browser.
        logger.error("unhandled_error: %s", exc.__class__.__name__, exc_info=True)
        return failure(
            ErrorCode.INTERNAL_ERROR,
            "An unexpected internal error occurred. Check the backend logs.",
            details=exc.__class__.__name__,
            status_code=500,
        )
