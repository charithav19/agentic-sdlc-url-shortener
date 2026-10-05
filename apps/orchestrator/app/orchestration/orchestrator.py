"""Sole transactional authority for workflow and stage status changes."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.governance.approvals import (
    ApprovalConflictError,
    ApprovalDecision,
    ApprovalNotFoundError,
    ApprovalResult,
    ApprovalStatus,
    ApprovalType,
    StaleApprovalError,
)
from app.observability.audit_store import AuditStore
from app.orchestration.commands import TransitionContext
from app.orchestration.contracts import StageStatus, WorkflowStatus
from app.orchestration.state_authority import orchestrator_transition
from app.orchestration.state_machine import (
    InvalidTransitionError,
    StaleTransitionError,
    require_stage_transition,
    require_workflow_transition,
)
from app.persistence.models import Approval, Artifact, StageRun, WorkflowRun
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
            verified = completion_verified
            if target is WorkflowStatus.COMPLETED:
                verified = verified and await self._has_current_release_approval(
                    session, workflow_id
                )
            return await self._transition_workflow_record(
                session,
                workflow,
                target,
                context,
                completion_verified=verified,
            )

    async def request_approval_checkpoint(
        self,
        workflow_id: uuid.UUID,
        *,
        approval_type: ApprovalType,
        artifact_id: uuid.UUID,
        artifact_version: int,
        context: TransitionContext,
    ) -> ApprovalResult:
        """Create an exact-version checkpoint and atomically pause a running workflow."""

        async with session_scope(self.session_factory) as session:
            workflow = await session.scalar(
                select(WorkflowRun).where(WorkflowRun.id == workflow_id).with_for_update()
            )
            if workflow is None:
                raise KeyError(f"Unknown workflow {workflow_id}")
            self._require_version(workflow.version, context.expected_version)
            artifact = await self._require_current_artifact(
                session, workflow_id, artifact_id, artifact_version
            )
            existing = await session.scalar(
                select(Approval)
                .where(
                    Approval.workflow_id == workflow_id,
                    Approval.approval_type == approval_type.value,
                    Approval.artifact_id == artifact_id,
                    Approval.artifact_version == artifact_version,
                    Approval.status.in_(
                        (ApprovalStatus.PENDING.value, ApprovalStatus.APPROVED.value)
                    ),
                )
                .order_by(Approval.created_at.desc())
                .limit(1)
                .with_for_update()
            )
            if existing is not None:
                if existing.status == ApprovalStatus.PENDING.value:
                    if workflow.status is WorkflowStatus.RUNNING:
                        await self._transition_workflow_record(
                            session,
                            workflow,
                            WorkflowStatus.WAITING_FOR_APPROVAL,
                            context,
                            completion_verified=False,
                        )
                    elif workflow.status is not WorkflowStatus.WAITING_FOR_APPROVAL:
                        raise ApprovalConflictError(
                            "Pending approval requires a running or waiting workflow"
                        )
                return self._approval_result(existing, workflow)

            if workflow.status not in {
                WorkflowStatus.RUNNING,
                WorkflowStatus.WAITING_FOR_APPROVAL,
            }:
                raise ApprovalConflictError(
                    "Approval checkpoint requires a running or waiting workflow"
                )
            approval = Approval(
                workflow_id=workflow_id,
                artifact_id=artifact.id,
                artifact_version=artifact.version,
                artifact_hash=artifact.content_sha256,
                approval_type=approval_type.value,
                status=ApprovalStatus.PENDING.value,
            )
            session.add(approval)
            await session.flush()
            await self.audit_store_factory(session).append(
                workflow_id,
                event_type="APPROVAL_REQUESTED",
                actor_type=context.actor_type,
                actor_id=context.actor_id,
                trace_id=context.trace_id,
                artifact_refs=[self._artifact_ref(artifact)],
                payload={
                    "approval_id": str(approval.id),
                    "approval_type": approval_type.value,
                },
            )
            if workflow.status is WorkflowStatus.RUNNING:
                await self._transition_workflow_record(
                    session,
                    workflow,
                    WorkflowStatus.WAITING_FOR_APPROVAL,
                    context,
                    completion_verified=False,
                )
            return self._approval_result(approval, workflow)

    async def decide_approval(
        self,
        workflow_id: uuid.UUID,
        *,
        approval_id: uuid.UUID,
        artifact_id: uuid.UUID,
        artifact_version: int,
        decision: ApprovalDecision,
        reviewer_id: str,
        reason: str | None,
        context: TransitionContext,
    ) -> ApprovalResult:
        """Persist a human decision and any resume transition in one transaction."""

        if context.actor_type != "HUMAN" or context.actor_id != reviewer_id:
            raise ApprovalConflictError("Approval decisions require the authenticated human actor")
        stale_message: str | None = None
        result: ApprovalResult | None = None
        async with session_scope(self.session_factory) as session:
            workflow = await session.scalar(
                select(WorkflowRun).where(WorkflowRun.id == workflow_id).with_for_update()
            )
            if workflow is None:
                raise KeyError(f"Unknown workflow {workflow_id}")
            approval = await session.scalar(
                select(Approval)
                .where(Approval.id == approval_id, Approval.workflow_id == workflow_id)
                .with_for_update()
            )
            if approval is None:
                raise ApprovalNotFoundError("Approval request was not found")
            if approval.artifact_id != artifact_id or approval.artifact_version != artifact_version:
                raise ApprovalConflictError(
                    "Approval artifact ID and version must exactly match the pending request"
                )

            if (
                approval.status == decision.value
                and approval.reviewer_id == reviewer_id
                and approval.reason == reason
            ):
                return self._approval_result(approval, workflow)
            self._require_version(workflow.version, context.expected_version)

            artifact = await self._current_artifact_or_none(
                session, workflow_id, artifact_id, artifact_version
            )
            if artifact is None:
                if approval.status != ApprovalStatus.INVALIDATED.value:
                    approval.status = ApprovalStatus.INVALIDATED.value
                    approval.decided_at = datetime.now(UTC)
                    approval.reason = "The referenced artifact is no longer current"
                    await self.audit_store_factory(session).append(
                        workflow_id,
                        event_type="APPROVAL_INVALIDATED",
                        actor_type="SYSTEM",
                        actor_id="orchestrator",
                        trace_id=context.trace_id,
                        artifact_refs=[
                            {
                                "id": str(approval.artifact_id),
                                "version": approval.artifact_version,
                                "sha256": approval.artifact_hash,
                            }
                        ],
                        reason=approval.reason,
                        payload={"approval_id": str(approval.id)},
                    )
                stale_message = "Approval references a stale artifact version"
                result = self._approval_result(approval, workflow)
            else:
                result = await self._apply_approval_decision(
                    session,
                    workflow,
                    approval,
                    artifact,
                    decision=decision,
                    reviewer_id=reviewer_id,
                    reason=reason,
                    context=context,
                )
        if stale_message is not None:
            raise StaleApprovalError(stale_message)
        if result is None:  # pragma: no cover - defensive invariant
            raise RuntimeError("Approval decision did not produce a result")
        return result

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
            if target is StageStatus.RUNNING and workflow.status is not WorkflowStatus.RUNNING:
                raise InvalidTransitionError(
                    f"Cannot start stage while workflow is {workflow.status.value}"
                )
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

    async def _apply_approval_decision(
        self,
        session: AsyncSession,
        workflow: WorkflowRun,
        approval: Approval,
        artifact: Artifact,
        *,
        decision: ApprovalDecision,
        reviewer_id: str,
        reason: str | None,
        context: TransitionContext,
    ) -> ApprovalResult:
        if approval.status != ApprovalStatus.PENDING.value:
            raise ApprovalConflictError(f"Approval has already been {approval.status.lower()}")
        if workflow.status is not WorkflowStatus.WAITING_FOR_APPROVAL:
            raise ApprovalConflictError("Workflow is not waiting for this approval")
        if decision is ApprovalDecision.REJECTED and (reason is None or not reason.strip()):
            raise ApprovalConflictError("A rejection reason is required")

        approval.status = decision.value
        approval.reviewer_id = reviewer_id
        approval.reason = reason
        approval.decided_at = datetime.now(UTC)
        await session.flush()
        await self.audit_store_factory(session).append(
            workflow.id,
            event_type="APPROVAL_DECIDED",
            actor_type="HUMAN",
            actor_id=reviewer_id,
            trace_id=context.trace_id,
            artifact_refs=[self._artifact_ref(artifact)],
            reason=reason,
            payload={
                "approval_id": str(approval.id),
                "approval_type": approval.approval_type,
                "status": decision.value,
            },
        )
        if decision is ApprovalDecision.APPROVED:
            other_pending = await session.scalar(
                select(func.count())
                .select_from(Approval)
                .where(
                    Approval.workflow_id == workflow.id,
                    Approval.id != approval.id,
                    Approval.status == ApprovalStatus.PENDING.value,
                )
            )
            if not other_pending:
                await self._transition_workflow_record(
                    session,
                    workflow,
                    WorkflowStatus.RUNNING,
                    context,
                    completion_verified=False,
                )
        return self._approval_result(approval, workflow)

    async def _transition_workflow_record(
        self,
        session: AsyncSession,
        workflow: WorkflowRun,
        target: WorkflowStatus,
        context: TransitionContext,
        *,
        completion_verified: bool,
    ) -> TransitionResult:
        previous = workflow.status
        require_workflow_transition(previous, target, completion_verified=completion_verified)
        with orchestrator_transition():
            workflow._status = target
        workflow.version += 1
        workflow.updated_at = datetime.now(UTC)
        event = await self.audit_store_factory(session).append(
            workflow.id,
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

    async def _require_current_artifact(
        self,
        session: AsyncSession,
        workflow_id: uuid.UUID,
        artifact_id: uuid.UUID,
        artifact_version: int,
    ) -> Artifact:
        artifact = await self._current_artifact_or_none(
            session, workflow_id, artifact_id, artifact_version
        )
        if artifact is None:
            raise StaleApprovalError("Artifact ID/version is missing or is no longer current")
        return artifact

    @staticmethod
    async def _current_artifact_or_none(
        session: AsyncSession,
        workflow_id: uuid.UUID,
        artifact_id: uuid.UUID,
        artifact_version: int,
    ) -> Artifact | None:
        artifact = await session.scalar(
            select(Artifact).where(
                Artifact.id == artifact_id,
                Artifact.workflow_id == workflow_id,
                Artifact.version == artifact_version,
            )
        )
        if artifact is None:
            return None
        latest = await session.scalar(
            select(func.max(Artifact.version)).where(
                Artifact.workflow_id == workflow_id,
                Artifact.logical_name == artifact.logical_name,
            )
        )
        return artifact if latest == artifact.version else None

    async def _has_current_release_approval(
        self, session: AsyncSession, workflow_id: uuid.UUID
    ) -> bool:
        approvals = await session.scalars(
            select(Approval).where(
                Approval.workflow_id == workflow_id,
                Approval.approval_type == ApprovalType.RELEASE.value,
                Approval.status == ApprovalStatus.APPROVED.value,
            )
        )
        for approval in approvals:
            if (
                await self._current_artifact_or_none(
                    session,
                    workflow_id,
                    approval.artifact_id,
                    approval.artifact_version,
                )
                is not None
            ):
                return True
        return False

    @staticmethod
    def _artifact_ref(artifact: Artifact) -> dict[str, str | int]:
        return {
            "id": str(artifact.id),
            "version": artifact.version,
            "sha256": artifact.content_sha256,
        }

    @staticmethod
    def _approval_result(approval: Approval, workflow: WorkflowRun) -> ApprovalResult:
        return ApprovalResult(
            approval_id=approval.id,
            workflow_id=workflow.id,
            approval_type=ApprovalType(approval.approval_type),
            status=ApprovalStatus(approval.status),
            artifact_id=approval.artifact_id,
            artifact_version=approval.artifact_version,
            artifact_hash=approval.artifact_hash,
            reviewer_id=approval.reviewer_id,
            reason=approval.reason,
            decided_at=approval.decided_at,
            workflow_status=workflow.status,
            workflow_version=workflow.version,
        )

    @staticmethod
    def _require_version(current: int, expected: int | None) -> None:
        if expected is not None and expected != current:
            raise StaleTransitionError(
                f"Stale transition version: expected {expected}, current {current}"
            )
