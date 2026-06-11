from typing import Any

import logging

from fastapi import FastAPI, HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("papermind.errors")


class APIError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details: Any | None = None) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


class NotFoundError(APIError):
    def __init__(self, message: str = "Resource not found", details: Any | None = None) -> None:
        super().__init__(status.HTTP_404_NOT_FOUND, "NOT_FOUND", message, details)


class ConflictError(APIError):
    def __init__(self, message: str = "Conflict", details: Any | None = None) -> None:
        super().__init__(status.HTTP_409_CONFLICT, "CONFLICT", message, details)


class DuplicateExactError(APIError):
    def __init__(self, message: str = "Document is already present", details: Any | None = None) -> None:
        super().__init__(status.HTTP_409_CONFLICT, "DUPLICATE_EXACT", message, details)


class BadRequestError(APIError):
    def __init__(self, message: str = "Bad request", details: Any | None = None) -> None:
        super().__init__(status.HTTP_400_BAD_REQUEST, "BAD_REQUEST", message, details)


class UnauthorizedError(APIError):
    def __init__(self, message: str = "Authentication required", details: Any | None = None) -> None:
        super().__init__(status.HTTP_401_UNAUTHORIZED, "UNAUTHORIZED", message, details)


class ForbiddenError(APIError):
    def __init__(self, message: str = "Insufficient permissions", details: Any | None = None) -> None:
        super().__init__(status.HTTP_403_FORBIDDEN, "FORBIDDEN", message, details)


class PayloadTooLargeError(APIError):
    def __init__(self, message: str = "Payload too large", details: Any | None = None) -> None:
        super().__init__(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "PAYLOAD_TOO_LARGE", message, details)


class StorageError(APIError):
    def __init__(self, message: str = "Storage error", details: Any | None = None) -> None:
        super().__init__(status.HTTP_500_INTERNAL_SERVER_ERROR, "STORAGE_ERROR", message, details)


def _error_payload(code: str, message: str, details: Any | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details}}


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def api_error_handler(_, exc: APIError) -> JSONResponse:
        details = exc.details if exc.status_code < 500 else None
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(exc.code, exc.message, details),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_payload(
                "VALIDATION_ERROR",
                "Request validation failed",
                exc.errors(),
            ),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_, exc: HTTPException) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else "Request failed"
        details = exc.detail if exc.status_code < 500 else None
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload("HTTP_ERROR", message, details),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_, exc: Exception) -> JSONResponse:
        logger.error("Unhandled API exception", exc_info=(type(exc), exc, exc.__traceback__))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_payload("INTERNAL_ERROR", "Internal server error"),
        )
