"""Database-backed readiness endpoint."""

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.api.dependencies import get_engine
from app.config import get_settings

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    status: str
    database: str


@router.get("/health", response_model=HealthResponse)
async def health(engine: Annotated[AsyncEngine, Depends(get_engine)]) -> HealthResponse:
    try:
        async with asyncio.timeout(get_settings().db_connect_timeout_seconds + 1):
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
    except Exception:
        logger.warning("database_health_check_failed")
        raise HTTPException(status_code=503, detail="Database unavailable") from None
    return HealthResponse(status="ok", database="up")
