"""Sole transactional authority for workflow and stage status changes."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.observability.audit_store import AuditStore
from app.orchestration.commands import TransitionContext
from app.orchestration.contracts import StageStatus, WorkflowStatus
from app.orchestration.state_authority import orchestrator_transition
from app.orchestration.state_machine import (
    StaleTransitionError,
    require_stage_transition,
    require_workflow_transition,
)
from app.persistence.models import StageRun, WorkflowRun
from app.persistence.session import session_scope

AuditStoreFactory = Callable[[AsyncSession], AuditStore]


@dataclass(frozen=True)
class TransitionResult:
    entity_id: uuid.UUID
    previous_status: str
    current_status: str
    version: int
    audit_event_id: uuid.UUID


class WorkflowOrchestrator:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        audit_store_factory: AuditStoreFactory = AuditStore,
    ) -> None:
        self.session_factory = session_factory
        self.audit_store_factory = audit_store_factory

    async def transition_workflow(
        self,
        workflow_id: uuid.UUID,
        target: WorkflowStatus,
        context: TransitionContext,
        *,
        completion_verified: bool = False,
    ) -> TransitionResult:
        async with session_scope(self.session_factory) as session:
            workflow = await session.scalar(
                select(WorkflowRun).where(WorkflowRun.id == workflow_id).with_for_update()
            )
            if workflow is None:
                raise KeyError(f"Unknown workflow {workflow_id}")
            self._require_version(workflow.version, context.expected_version)
            previous = workflow.status
            require_workflow_transition(previous, target, completion_verified=completion_verified)
            with orchestrator_transition():
                workflow._status = target
            workflow.version += 1
            workflow.updated_at = datetime.now(UTC)
            event = await self.audit_store_factory(session).append(
                workflow_id,
                event_type="WORKFLOW_STATUS_CHANGED",
                actor_type=context.actor_type,
                actor_id=context.actor_id,
                trace_id=context.trace_id,
                before_state=previous.value,
                after_state=target.value,
                reason=context.reason,
                payload={"entity_version": workflow.version},
            )
            return TransitionResult(
                entity_id=workflow.id,
                previous_status=previous.value,
                current_status=target.value,
                version=workflow.version,
                audit_event_id=event.id,
            )

    async def transition_stage(
        self,
        stage_run_id: uuid.UUID,
        target: StageStatus,
        context: TransitionContext,
    ) -> TransitionResult:
        async with session_scope(self.session_factory) as session:
            stage_identity = await session.execute(
                select(StageRun.workflow_id).where(StageRun.id == stage_run_id)
            )
            workflow_id = stage_identity.scalar_one_or_none()
            if workflow_id is None:
                raise KeyError(f"Unknown stage run {stage_run_id}")
            workflow = await session.scalar(
                select(WorkflowRun).where(WorkflowRun.id == workflow_id).with_for_update()
            )
            if workflow is None:
                raise KeyError(f"Unknown workflow {workflow_id}")
            stage = await session.scalar(
                select(StageRun).where(StageRun.id == stage_run_id).with_for_update()
            )
            if stage is None:
                raise KeyError(f"Unknown stage run {stage_run_id}")
            self._require_version(stage.version, context.expected_version)
            previous = stage.status
            require_stage_transition(previous, target)
            now = datetime.now(UTC)
            with orchestrator_transition():
                stage._status = target
            stage.version += 1
            if target == StageStatus.RUNNING and stage.started_at is None:
                stage.started_at = now
            if target in {
                StageStatus.SUCCEEDED,
                StageStatus.FAILED,
                StageStatus.ROLLED_BACK,
                StageStatus.SKIPPED,
                StageStatus.SAFE_STOPPED,
                StageStatus.CANCELLED,
            }:
                stage.completed_at = now
            if target == StageStatus.SUCCEEDED:
                workflow.last_successful_stage = stage.stage_name
            event = await self.audit_store_factory(session).append(
                workflow_id,
                event_type="STAGE_STATUS_CHANGED",
                actor_type=context.actor_type,
                actor_id=context.actor_id,
                stage_run_id=stage.id,
                trace_id=context.trace_id,
                before_state=previous.value,
                after_state=target.value,
                reason=context.reason,
                payload={
                    "entity_version": stage.version,
                    "stage_name": stage.stage_name,
                    "generation": stage.generation,
                    "attempt": stage.attempt,
                },
            )
            return TransitionResult(
                entity_id=stage.id,
                previous_status=previous.value,
                current_status=target.value,
                version=stage.version,
                audit_event_id=event.id,
            )

    @staticmethod
    def _require_version(current: int, expected: int | None) -> None:
        if expected is not None and expected != current:
            raise StaleTransitionError(
                f"Stale transition version: expected {expected}, current {current}"
            )
