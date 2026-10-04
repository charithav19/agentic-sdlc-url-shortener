"""Append and page durable per-workflow audit events."""

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.models import AuditEvent, StageRun, WorkflowRun


class AuditStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def append(
        self,
        workflow_id: uuid.UUID,
        *,
        event_type: str,
        actor_type: str,
        actor_id: str,
        stage_run_id: uuid.UUID | None = None,
        trace_id: uuid.UUID | None = None,
        before_state: str | None = None,
        after_state: str | None = None,
        artifact_refs: list[dict[str, Any]] | None = None,
        reason: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> AuditEvent:
        workflow = await self.session.scalar(
            select(WorkflowRun).where(WorkflowRun.id == workflow_id).with_for_update()
        )
        if workflow is None:
            raise KeyError(f"Unknown workflow {workflow_id}")
        if stage_run_id is not None:
            stage = await self.session.get(StageRun, stage_run_id)
            if stage is None or stage.workflow_id != workflow_id:
                raise ValueError("Audit stage must belong to the workflow")
        last_sequence = await self.session.scalar(
            select(func.max(AuditEvent.sequence)).where(AuditEvent.workflow_id == workflow_id)
        )
        event = AuditEvent(
            workflow_id=workflow_id,
            stage_run_id=stage_run_id,
            sequence=(last_sequence or 0) + 1,
            trace_id=trace_id,
            actor_type=actor_type,
            actor_id=actor_id,
            event_type=event_type,
            before_state=before_state,
            after_state=after_state,
            artifact_refs=artifact_refs or [],
            reason=reason,
            payload=payload or {},
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def page(
        self, workflow_id: uuid.UUID, *, after_sequence: int = 0, limit: int = 100
    ) -> list[AuditEvent]:
        if not 1 <= limit <= 500:
            raise ValueError("Audit page limit must be between 1 and 500")
        result = await self.session.scalars(
            select(AuditEvent)
            .where(
                AuditEvent.workflow_id == workflow_id,
                AuditEvent.sequence > after_sequence,
            )
            .order_by(AuditEvent.sequence)
            .limit(limit)
        )
        return list(result)
