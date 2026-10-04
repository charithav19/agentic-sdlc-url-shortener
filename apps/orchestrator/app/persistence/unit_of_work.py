"""Single database transaction for provenance writes and their audit events."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.artifacts.store import ArtifactStore
from app.observability.audit_store import AuditStore
from app.persistence.repositories import (
    ApprovalRepository,
    DecisionRepository,
    LineageRepository,
    StageRunRepository,
    WorkflowRepository,
)
from app.persistence.session import session_scope


class UnitOfWork:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.workflows = WorkflowRepository(session)
        self.stages = StageRunRepository(session)
        self.artifacts = ArtifactStore(session)
        self.lineage = LineageRepository(session)
        self.decisions = DecisionRepository(session)
        self.approvals = ApprovalRepository(session)
        self.audit = AuditStore(session)

    @classmethod
    @asynccontextmanager
    async def open(
        cls, session_factory: async_sessionmaker[AsyncSession]
    ) -> AsyncIterator["UnitOfWork"]:
        async with session_scope(session_factory) as session:
            yield cls(session)
