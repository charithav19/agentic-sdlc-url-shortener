"""FastAPI application and resource lifecycle."""

import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.api.approvals import router as approvals_router
from app.api.errors import register_error_handlers
from app.api.health import router as health_router
from app.api.recovery import router as recovery_router
from app.config import get_settings
from app.observability.logging import configure_logging
from app.persistence.session import create_database_engine, create_session_factory


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    engine = create_database_engine(settings)
    application.state.db_engine = engine
    application.state.session_factory = create_session_factory(engine)
    try:
        yield
    finally:
        await engine.dispose()


app = FastAPI(
    title="Agentic SDLC Orchestrator",
    version="0.1.0",
    description="Deterministic SDLC orchestration, readiness, and human approval API.",
    lifespan=lifespan,
)
app.include_router(health_router)
app.include_router(approvals_router)
app.include_router(recovery_router)
register_error_handlers(app)


@app.middleware("http")
async def trace_requests(request: Request, call_next):
    trace_id = str(uuid.uuid4())
    request.state.trace_id = trace_id
    response = await call_next(request)
    response.headers["X-Trace-Id"] = trace_id
    logging.getLogger("app.http").info(
        "request_complete",
        extra={
            "trace_id": trace_id,
            "http_method": request.method,
            "http_path": request.url.path,
            "http_status": response.status_code,
        },
    )
    return response
