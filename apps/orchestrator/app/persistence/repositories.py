"""Internal repositories for creating and reading Phase 6 records."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.artifacts.schemas import ArtifactRef
from app.governance.approvals import ApprovalStatus, ApprovalType
from app.orchestration.contracts import ScenarioType, StageStatus, WorkflowStatus
from app.persistence.models import (
    Approval,
    Artifact,
    Decision,
    StageRun,
    WorkflowRun,
)


class WorkflowRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        scenario_type: ScenarioType,
        provider_mode: str,
        workspace_ref: str,
    ) -> WorkflowRun:
        workflow = WorkflowRun(
            scenario_type=scenario_type,
            _status=WorkflowStatus.CREATED,
            provider_mode=provider_mode,
            workspace_ref=workspace_ref,
            requirement_version=1,
            generation=1,
            version=1,
        )
        self.session.add(workflow)
        await self.session.flush()
        return workflow

    async def get(self, workflow_id: uuid.UUID) -> WorkflowRun:
        workflow = await self.session.get(WorkflowRun, workflow_id)
        if workflow is None:
            raise KeyError(f"Unknown workflow {workflow_id}")
        return workflow


class StageRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_attempt(
        self,
        workflow_id: uuid.UUID,
        *,
        stage_name: str,
        generation: int,
        attempt: int,
        executor: str,
        input_artifacts: list[ArtifactRef] | None = None,
    ) -> StageRun:
        workflow = await self.session.scalar(
            select(WorkflowRun).where(WorkflowRun.id == workflow_id).with_for_update()
        )
        if workflow is None:
            raise KeyError(f"Unknown workflow {workflow_id}")
        if generation > workflow.generation or generation < 1 or attempt < 1:
            raise ValueError("Invalid stage generation or attempt")
        refs: list[dict[str, Any]] = []
        for ref in input_artifacts or []:
            artifact = await self.session.get(Artifact, ref.id)
            if (
                artifact is None
                or artifact.workflow_id != workflow_id
                or artifact.version != ref.version
                or artifact.content_sha256 != ref.sha256
            ):
                raise ValueError("Input artifact reference does not match an exact version")
            refs.append({"id": str(ref.id), "version": ref.version, "sha256": ref.sha256})
        stage = StageRun(
            workflow_id=workflow_id,
            stage_name=stage_name,
            generation=generation,
            attempt=attempt,
            _status=StageStatus.PENDING,
            executor=executor,
            input_artifact_refs=refs,
            version=1,
        )
        self.session.add(stage)
        await self.session.flush()
        return stage

    async def get(self, stage_run_id: uuid.UUID) -> StageRun:
        stage = await self.session.get(StageRun, stage_run_id)
        if stage is None:
            raise KeyError(f"Unknown stage run {stage_run_id}")
        return stage


class DecisionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(
        self,
        workflow_id: uuid.UUID,
        *,
        decision_type: str,
        outcome: str,
        rationale: str,
        actor_type: str,
        actor_id: str,
        stage_run_id: uuid.UUID | None = None,
        alternatives: list[dict[str, Any]] | None = None,
        related_artifact_ids: list[uuid.UUID] | None = None,
        requirement_ids: list[str] | None = None,
    ) -> Decision:
        if stage_run_id is not None:
            stage = await self.session.get(StageRun, stage_run_id)
            if stage is None or stage.workflow_id != workflow_id:
                raise ValueError("Decision stage must belong to the workflow")
        for artifact_id in related_artifact_ids or []:
            artifact = await self.session.get(Artifact, artifact_id)
            if artifact is None or artifact.workflow_id != workflow_id:
                raise ValueError("Decision artifact must belong to the workflow")
        decision = Decision(
            workflow_id=workflow_id,
            stage_run_id=stage_run_id,
            decision_type=decision_type,
            outcome=outcome,
            rationale=rationale,
            alternatives=alternatives or [],
            actor_type=actor_type,
            actor_id=actor_id,
            related_artifact_ids=[str(value) for value in related_artifact_ids or []],
            requirement_ids=requirement_ids or [],
        )
        self.session.add(decision)
        await self.session.flush()
        return decision


class ApprovalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def request(
        self, workflow_id: uuid.UUID, *, artifact_id: uuid.UUID, approval_type: str
    ) -> Approval:
        approval_kind = ApprovalType(approval_type)
        artifact = await self.session.get(Artifact, artifact_id)
        if artifact is None or artifact.workflow_id != workflow_id:
            raise ValueError("Approval artifact must belong to the workflow")
        approval = Approval(
            workflow_id=workflow_id,
            artifact_id=artifact_id,
            artifact_version=artifact.version,
            artifact_hash=artifact.content_sha256,
            approval_type=approval_kind.value,
            status=ApprovalStatus.PENDING.value,
        )
        self.session.add(approval)
        await self.session.flush()
        return approval

    async def invalidate_for_new_artifact(self, artifact: Artifact) -> list[Approval]:
        """Invalidate active decisions attached to older versions of this logical artifact."""

        approved_artifact = aliased(Artifact)
        result = await self.session.scalars(
            select(Approval)
            .join(approved_artifact, approved_artifact.id == Approval.artifact_id)
            .where(
                Approval.workflow_id == artifact.workflow_id,
                approved_artifact.logical_name == artifact.logical_name,
                approved_artifact.version < artifact.version,
                Approval.status.in_((ApprovalStatus.PENDING.value, ApprovalStatus.APPROVED.value)),
            )
            .with_for_update()
        )
        invalidated = list(result)
        now = datetime.now(UTC)
        for approval in invalidated:
            approval.status = ApprovalStatus.INVALIDATED.value
            approval.decided_at = now
            approval.reason = "A newer artifact version was created"
        if invalidated:
            await self.session.flush()
        return invalidated
