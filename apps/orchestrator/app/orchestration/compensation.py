"""Idempotent semantic compensation for rejected implementation candidates."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.artifacts.candidate_refs import ArtifactStatus
from app.governance.approvals import ApprovalStatus
from app.observability.audit_store import AuditStore
from app.orchestration.commands import TransitionContext
from app.orchestration.contracts import StageStatus
from app.persistence.models import (
    Approval,
    Artifact,
    ArtifactLifecycle,
    CandidateReference,
    Compensation,
    StageRun,
    WorkflowRun,
)
from app.persistence.session import session_scope

MANDATORY_VALIDATION_STAGES = frozenset(
    {"BUILD_VALIDATION", "UNIT_TEST", "INTEGRATION_TEST", "SECURITY_VALIDATION"}
)


@dataclass(frozen=True)
class CompensationResult:
    compensation_id: uuid.UUID
    candidate_artifact_id: uuid.UUID
    restored_artifact_id: uuid.UUID | None
    idempotent: bool


class CompensationCoordinator:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def compensate_active_candidate_for_stage(
        self,
        stage_run_id: uuid.UUID,
        *,
        failure_reason: str,
        context: TransitionContext,
    ) -> CompensationResult | None:
        candidate_id = await self._active_candidate_input(stage_run_id)
        if candidate_id is None:
            return None
        return await self.compensate(
            stage_run_id,
            candidate_artifact_id=candidate_id,
            failure_reason=failure_reason,
            context=context,
        )

    async def compensate(
        self,
        stage_run_id: uuid.UUID,
        *,
        candidate_artifact_id: uuid.UUID,
        failure_reason: str,
        context: TransitionContext,
    ) -> CompensationResult:
        async with session_scope(self.session_factory) as session:
            stage = await session.scalar(
                select(StageRun).where(StageRun.id == stage_run_id).with_for_update()
            )
            if stage is None:
                raise KeyError(f"Unknown validation stage {stage_run_id}")
            workflow = await session.scalar(
                select(WorkflowRun).where(WorkflowRun.id == stage.workflow_id).with_for_update()
            )
            if workflow is None:
                raise KeyError(f"Unknown workflow {stage.workflow_id}")
            existing = await session.scalar(
                select(Compensation)
                .where(
                    Compensation.workflow_id == workflow.id,
                    Compensation.candidate_artifact_id == candidate_artifact_id,
                    Compensation.cause_stage_run_id == stage.id,
                )
                .with_for_update()
            )
            if existing is not None and existing.status == "COMPLETED":
                return CompensationResult(
                    existing.id,
                    existing.candidate_artifact_id,
                    existing.restored_artifact_id,
                    True,
                )
            if stage.stage_name not in MANDATORY_VALIDATION_STAGES or stage.status not in {
                StageStatus.FAILED,
                StageStatus.SAFE_STOPPED,
            }:
                raise ValueError("Compensation requires a failed mandatory validation stage")
            candidate = await session.scalar(
                select(Artifact)
                .where(
                    Artifact.id == candidate_artifact_id,
                    Artifact.workflow_id == workflow.id,
                )
                .with_for_update()
            )
            lifecycle = await session.scalar(
                select(ArtifactLifecycle)
                .where(
                    ArtifactLifecycle.artifact_id == candidate_artifact_id,
                    ArtifactLifecycle.workflow_id == workflow.id,
                )
                .with_for_update()
            )
            if candidate is None or lifecycle is None:
                raise ValueError("Candidate lifecycle metadata is missing")
            reference = await session.scalar(
                select(CandidateReference)
                .where(
                    CandidateReference.workflow_id == workflow.id,
                    CandidateReference.logical_name == candidate.logical_name,
                )
                .with_for_update()
            )
            if (
                reference is None
                or reference.active_artifact_id != candidate.id
                or lifecycle.status != ArtifactStatus.CANDIDATE.value
            ):
                raise ValueError("Only the active candidate can be compensated")
            previous_id = reference.approved_artifact_id
            compensation = existing or Compensation(
                workflow_id=workflow.id,
                candidate_artifact_id=candidate.id,
                cause_stage_run_id=stage.id,
                previous_approved_artifact_id=previous_id,
                status="STARTED",
                failure_reason=failure_reason,
            )
            if existing is None:
                session.add(compensation)
            await session.flush()
            candidate_ref = self._artifact_ref(candidate)
            previous = await self._approved_previous(session, workflow.id, previous_id)
            previous_ref = self._artifact_ref(previous) if previous is not None else None
            refs = [candidate_ref, *([previous_ref] if previous_ref else [])]
            audit = AuditStore(session)
            await audit.append(
                workflow.id,
                event_type="ROLLBACK_STARTED",
                actor_type=context.actor_type,
                actor_id=context.actor_id,
                stage_run_id=stage.id,
                trace_id=context.trace_id,
                artifact_refs=refs,
                reason=failure_reason,
                payload={
                    "compensation_id": str(compensation.id),
                    "candidate_artifact_id": str(candidate.id),
                    "cause_stage": stage.stage_name,
                },
            )
            lifecycle.status = ArtifactStatus.ROLLED_BACK.value
            lifecycle.active = False
            lifecycle.version += 1
            reference.active_artifact_id = previous.id if previous is not None else None
            reference.version += 1
            if previous is not None:
                previous_lifecycle = await session.scalar(
                    select(ArtifactLifecycle)
                    .where(ArtifactLifecycle.artifact_id == previous.id)
                    .with_for_update()
                )
                if previous_lifecycle is None:
                    raise ValueError("Approved candidate lifecycle metadata is missing")
                previous_lifecycle.active = True
                previous_lifecycle.version += 1
            await self._invalidate_candidate_approvals(
                session, workflow.id, candidate.id, audit, context
            )
            compensation.status = "COMPLETED"
            compensation.restored_artifact_id = previous.id if previous is not None else None
            compensation.completed_at = datetime.now(UTC)
            await audit.append(
                workflow.id,
                event_type="ROLLBACK_COMPLETED",
                actor_type=context.actor_type,
                actor_id=context.actor_id,
                stage_run_id=stage.id,
                trace_id=context.trace_id,
                artifact_refs=refs,
                reason=failure_reason,
                payload={
                    "compensation_id": str(compensation.id),
                    "candidate_status": ArtifactStatus.ROLLED_BACK.value,
                    "restored_artifact_id": str(previous.id) if previous else None,
                },
            )
            return CompensationResult(compensation.id, candidate.id, previous_id, False)

    async def _active_candidate_input(self, stage_run_id: uuid.UUID) -> uuid.UUID | None:
        async with session_scope(self.session_factory) as session:
            stage = await session.get(StageRun, stage_run_id)
            if stage is None or stage.stage_name not in MANDATORY_VALIDATION_STAGES:
                return None
            input_ids: list[uuid.UUID] = []
            for ref in stage.input_artifact_refs:
                try:
                    input_ids.append(uuid.UUID(str(ref["id"])))
                except (KeyError, TypeError, ValueError):
                    continue
            if not input_ids:
                return None
            return await session.scalar(
                select(CandidateReference.active_artifact_id)
                .join(
                    ArtifactLifecycle,
                    ArtifactLifecycle.artifact_id == CandidateReference.active_artifact_id,
                )
                .where(
                    CandidateReference.workflow_id == stage.workflow_id,
                    CandidateReference.active_artifact_id.in_(input_ids),
                    ArtifactLifecycle.status == ArtifactStatus.CANDIDATE.value,
                    ArtifactLifecycle.active.is_(True),
                )
                .limit(1)
            )

    @staticmethod
    async def _approved_previous(
        session: AsyncSession, workflow_id: uuid.UUID, artifact_id: uuid.UUID | None
    ) -> Artifact | None:
        if artifact_id is None:
            return None
        artifact = await session.scalar(
            select(Artifact).where(
                Artifact.id == artifact_id,
                Artifact.workflow_id == workflow_id,
            )
        )
        lifecycle = await session.get(ArtifactLifecycle, artifact_id)
        if (
            artifact is None
            or lifecycle is None
            or lifecycle.status != ArtifactStatus.APPROVED.value
        ):
            raise ValueError("Previous candidate is not approved")
        return artifact

    @staticmethod
    async def _invalidate_candidate_approvals(
        session: AsyncSession,
        workflow_id: uuid.UUID,
        candidate_id: uuid.UUID,
        audit: AuditStore,
        context: TransitionContext,
    ) -> None:
        approvals = list(
            await session.scalars(
                select(Approval)
                .where(
                    Approval.workflow_id == workflow_id,
                    Approval.artifact_id == candidate_id,
                    Approval.status.in_(
                        (ApprovalStatus.PENDING.value, ApprovalStatus.APPROVED.value)
                    ),
                )
                .with_for_update()
            )
        )
        for approval in approvals:
            approval.status = ApprovalStatus.INVALIDATED.value
            approval.reason = "Candidate was rolled back after mandatory validation failure"
            approval.decided_at = datetime.now(UTC)
            await audit.append(
                workflow_id,
                event_type="APPROVAL_INVALIDATED",
                actor_type=context.actor_type,
                actor_id=context.actor_id,
                trace_id=context.trace_id,
                reason=approval.reason,
                payload={"approval_id": str(approval.id), "rollback": True},
            )

    @staticmethod
    def _artifact_ref(artifact: Artifact) -> dict[str, str | int]:
        return {
            "id": str(artifact.id),
            "version": artifact.version,
            "sha256": artifact.content_sha256,
        }
