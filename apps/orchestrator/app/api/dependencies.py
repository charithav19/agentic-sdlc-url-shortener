"""Shared HTTP dependencies."""

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.orchestration.orchestrator import WorkflowOrchestrator
from app.persistence.session import session_scope


def get_engine(request: Request) -> AsyncEngine:
    return request.app.state.db_engine


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with session_scope(request.app.state.session_factory) as session:
        yield session


def get_orchestrator(request: Request) -> WorkflowOrchestrator:
    return WorkflowOrchestrator(request.app.state.session_factory)
