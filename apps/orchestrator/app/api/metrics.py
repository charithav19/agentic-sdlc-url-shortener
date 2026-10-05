"""Prometheus endpoint for durable orchestration metrics."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_session
from app.observability.metrics import render_prometheus
from app.observability.reporting import MetricsReporter

router = APIRouter(tags=["observability"])


@router.get("/metrics", include_in_schema=False)
async def metrics_endpoint(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    snapshot = await MetricsReporter(session).snapshot()
    return Response(
        content=render_prometheus(snapshot),
        media_type="text/plain; version=0.0.4",
    )
