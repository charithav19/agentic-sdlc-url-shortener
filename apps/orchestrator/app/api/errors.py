"""Public error envelopes that do not expose internal exception details."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException


def _error(request: Request, status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {"code": code, "message": message},
            "traceId": getattr(request.state, "trace_id", None),
        },
    )


def register_error_handlers(application: FastAPI) -> None:
    @application.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        return _error(request, exc.status_code, "HTTP_ERROR", str(exc.detail))

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, _exc: RequestValidationError) -> JSONResponse:
        return _error(request, 422, "VALIDATION_ERROR", "Request validation failed")

    @application.exception_handler(Exception)
    async def unexpected_error(request: Request, _exc: Exception) -> JSONResponse:
        return _error(request, 500, "INTERNAL_ERROR", "Internal server error")
