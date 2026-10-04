"""Internal creation service; status transitions are reserved for Phase 9."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.artifacts.schemas import ArtifactInput, ArtifactRef
from app.orchestration.contracts import ScenarioType, WorkflowStatus
from app.persistence.unit_of_work import UnitOfWork
from app.tools.workspaces import WorkspaceManager


class WorkflowPersistenceService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        workspaces: WorkspaceManager | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.workspaces = workspaces or WorkspaceManager()

    async def create_workflow(
        self, *, scenario_type: ScenarioType, provider_mode: str, workspace_ref: str
    ) -> uuid.UUID:
        async with UnitOfWork.open(self.session_factory) as unit:
            workflow = await unit.workflows.create(
                scenario_type=scenario_type,
                provider_mode=provider_mode,
                workspace_ref=workspace_ref,
            )
            # Caller-supplied workspace_ref is a seed label, never a filesystem path.
            with self.workspaces.for_workflow(workflow.id):
                workflow.workspace_ref = f"workspaces/{workflow.id}"
            await unit.audit.append(
                workflow.id,
                event_type="WORKFLOW_CREATED",
                actor_type="SYSTEM",
                actor_id="orchestrator",
                after_state=WorkflowStatus.CREATED.value,
                payload={"workspace": workflow.workspace_ref, "seed_ref": workspace_ref},
            )
            return workflow.id

    async def add_stage_attempt(
        self,
        workflow_id: uuid.UUID,
        *,
        stage_name: str,
        generation: int,
        attempt: int,
        executor: str,
        input_artifacts: list[ArtifactRef] | None = None,
    ) -> uuid.UUID:
        async with UnitOfWork.open(self.session_factory) as unit:
            stage = await unit.stages.add_attempt(
                workflow_id,
                stage_name=stage_name,
                generation=generation,
                attempt=attempt,
                executor=executor,
                input_artifacts=input_artifacts,
            )
            await unit.audit.append(
                workflow_id,
                event_type="STAGE_ATTEMPT_CREATED",
                actor_type="SYSTEM",
                actor_id="orchestrator",
                stage_run_id=stage.id,
                after_state=stage.status.value,
                payload={
                    "stage_name": stage_name,
                    "generation": generation,
                    "attempt": attempt,
                },
            )
            return stage.id

    async def store_artifact(
        self, workflow_id: uuid.UUID, artifact_input: ArtifactInput
    ) -> ArtifactRef:
        async with UnitOfWork.open(self.session_factory) as unit:
            artifact = await unit.artifacts.put(workflow_id, artifact_input)
            ref = ArtifactRef(
                id=artifact.id, version=artifact.version, sha256=artifact.content_sha256
            )
            await unit.audit.append(
                workflow_id,
                event_type="ARTIFACT_VERSION_CREATED",
                actor_type="SYSTEM",
                actor_id="orchestrator",
                stage_run_id=artifact.producer_stage_run_id,
                artifact_refs=[ref.model_dump(mode="json")],
            )
            return ref

    async def request_approval(
        self, workflow_id: uuid.UUID, *, artifact_id: uuid.UUID, approval_type: str
    ) -> uuid.UUID:
        async with UnitOfWork.open(self.session_factory) as unit:
            approval = await unit.approvals.request(
                workflow_id, artifact_id=artifact_id, approval_type=approval_type
            )
            await unit.audit.append(
                workflow_id,
                event_type="APPROVAL_REQUESTED",
                actor_type="SYSTEM",
                actor_id="orchestrator",
                artifact_refs=[
                    {
                        "id": str(approval.artifact_id),
                        "version": approval.artifact_version,
                        "sha256": approval.artifact_hash,
                    }
                ],
            )
            return approval.id

    async def link_artifacts(
        self,
        workflow_id: uuid.UUID,
        *,
        parent_artifact_id: uuid.UUID,
        child_artifact_id: uuid.UUID,
        relationship: str,
        requirement_ids: list[str] | None = None,
        component_ids: list[str] | None = None,
    ) -> uuid.UUID:
        async with UnitOfWork.open(self.session_factory) as unit:
            edge = await unit.lineage.add(
                workflow_id,
                parent_artifact_id=parent_artifact_id,
                child_artifact_id=child_artifact_id,
                relationship=relationship,
                requirement_ids=requirement_ids,
                component_ids=component_ids,
            )
            await unit.audit.append(
                workflow_id,
                event_type="ARTIFACT_LINEAGE_CREATED",
                actor_type="SYSTEM",
                actor_id="orchestrator",
                artifact_refs=[
                    {"id": str(parent_artifact_id)},
                    {"id": str(child_artifact_id)},
                ],
            )
            return edge.id

    async def record_decision(
        self,
        workflow_id: uuid.UUID,
        *,
        decision_type: str,
        outcome: str,
        rationale: str,
        actor_type: str,
        actor_id: str,
        related_artifact_ids: list[uuid.UUID] | None = None,
        requirement_ids: list[str] | None = None,
    ) -> uuid.UUID:
        async with UnitOfWork.open(self.session_factory) as unit:
            decision = await unit.decisions.add(
                workflow_id,
                decision_type=decision_type,
                outcome=outcome,
                rationale=rationale,
                actor_type=actor_type,
                actor_id=actor_id,
                related_artifact_ids=related_artifact_ids,
                requirement_ids=requirement_ids,
            )
            await unit.audit.append(
                workflow_id,
                event_type="DECISION_RECORDED",
                actor_type=actor_type,
                actor_id=actor_id,
                artifact_refs=[{"id": str(value)} for value in related_artifact_ids or []],
                reason=rationale,
                payload={"decision_id": str(decision.id), "outcome": outcome},
            )
            return decision.id
