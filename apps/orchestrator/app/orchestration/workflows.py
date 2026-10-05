"""Workflow creation and read projections over the existing domain services."""

import uuid
from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.artifacts.schemas import ArtifactInput
from app.artifacts.store import canonical_content
from app.orchestration.contracts import ScenarioType, StageStatus, WorkflowStatus
from app.orchestration.dependencies import StageDependencyResolver
from app.orchestration.graph import StageDefinition, WorkflowGraph, build_graph
from app.orchestration.graph_loader import load_graph
from app.persistence.models import (
    Approval,
    Artifact,
    ArtifactLifecycle,
    AuditEvent,
    StageRun,
    WorkflowRun,
)
from app.persistence.session import session_scope
from app.persistence.unit_of_work import UnitOfWork
from app.scenarios.fixtures import ScenarioFixtureLoader
from app.scenarios.runner import ScenarioFixtureRunner
from app.tools.workspaces import WorkspaceManager


def camel_case(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(word.capitalize() for word in rest)


class Document(BaseModel):
    model_config = ConfigDict(alias_generator=camel_case, populate_by_name=True, extra="forbid")


class CreateWorkflow(Document):
    scenario: ScenarioType
    requirement: str | None = Field(default=None, min_length=1, max_length=32000)
    provider_mode: Literal["fake", "openai"] = "fake"
    seed_ref: str | None = Field(default=None, max_length=256)
    demo: bool = False

    @model_validator(mode="after")
    def explicit_requirement(self) -> Self:
        if not self.demo and (self.requirement is None or not self.requirement.strip()):
            raise ValueError("A nonblank requirement is required outside demo mode")
        if self.requirement is not None and not self.requirement.strip():
            raise ValueError("Requirement cannot be blank")
        return self


class StageView(Document):
    stage_run_id: uuid.UUID | None = None
    stage_name: str
    status: StageStatus
    generation: int
    attempt: int
    version: int
    dependencies: list[str]
    unmet_dependencies: list[str]
    blocked_reason: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ArtifactView(Document):
    artifact_id: uuid.UUID
    logical_name: str
    artifact_type: str
    version: int
    sha256: str
    status: str


class HumanAction(Document):
    kind: str
    approval_id: uuid.UUID | None = None
    approval_type: str | None = None
    artifact_id: uuid.UUID
    artifact_version: int
    artifact_hash: str
    questions: list[str] = Field(default_factory=list)


class WorkflowView(Document):
    workflow_id: uuid.UUID
    scenario_type: ScenarioType
    provider_mode: str
    status: WorkflowStatus
    workflow_version: int
    state_version: int
    generation: int
    requirement_version: int
    graph_hash: str
    graph_version: str
    graph_revision_id: uuid.UUID
    stages: list[StageView]
    blockers: list[str]
    pending_human_action: list[HumanAction]
    artifacts: list[ArtifactView]
    next_action: str
    last_successful_stage: str | None
    stop_reason: str | None
    created_at: datetime


class GraphView(Document):
    workflow_id: uuid.UUID
    workflow_version: int
    generation: int
    version: str
    graph_hash: str
    graph_revision_id: uuid.UUID
    stages: list[dict]
    current_stages: list[str]
    blocked_stages: list[str]
    ready_stages: list[str]


def graph_document(graph: WorkflowGraph) -> dict:
    return {"version": graph.version, "stages": [s.model_dump(mode="json") for s in graph.stages]}


class WorkflowService:
    def __init__(
        self,
        factory: async_sessionmaker[AsyncSession],
        *,
        workspaces: WorkspaceManager,
        loader: ScenarioFixtureLoader,
    ) -> None:
        self.factory = factory
        self.workspaces = workspaces
        self.loader = loader

    async def create(self, command: CreateWorkflow, *, trace_id: uuid.UUID) -> uuid.UUID:
        fixture = self.loader.load(command.scenario)
        # A seed is a server-owned selector, never a client filesystem path.
        allowed_seeds = {
            command.scenario.value.lower(),
            f"scenarios/{command.scenario.value.lower()}/seed",
        }
        if command.seed_ref is not None and command.seed_ref not in allowed_seeds:
            raise ValueError("seedRef must select the server-owned seed for this scenario")
        requirement = (command.requirement or fixture.requirement).strip()
        graph = load_graph()
        conditional = load_graph(blocking_ambiguity=True)
        async with UnitOfWork.open(self.factory) as unit:
            workflow = await unit.workflows.create(
                scenario_type=command.scenario,
                provider_mode=command.provider_mode,
                workspace_ref="pending",
            )
            prepared = ScenarioFixtureRunner(
                loader=self.loader, workspaces=self.workspaces
            ).prepare(command.scenario, workflow.id)
            workflow.workspace_ref = f"workspaces/{workflow.id}"
            await unit.audit.append(
                workflow.id,
                event_type="WORKFLOW_CREATED",
                actor_type="SYSTEM",
                actor_id="workflow-api",
                trace_id=trace_id,
                after_state=WorkflowStatus.CREATED.value,
                payload={
                    "seed_ref": command.seed_ref,
                    "demo": command.demo,
                    "provider_mode": command.provider_mode,
                    "seed_sha256": prepared.seed_sha256,
                },
            )
            requirement_artifact = await unit.artifacts.put(
                workflow.id,
                ArtifactInput(
                    logical_name="requirement",
                    artifact_type="requirement",
                    schema_version="1",
                    content={"requirement": requirement},
                    requirement_ids=["REQ-WORKFLOW"],
                    component_ids=["URL-SHORTENER"],
                ),
            )
            revision = await unit.artifacts.put(
                workflow.id,
                ArtifactInput(
                    logical_name="workflow-graph",
                    artifact_type="workflow_graph",
                    schema_version="1",
                    content={
                        "base": graph_document(graph),
                        "conditional": graph_document(conditional),
                    },
                ),
            )
            workflow.graph_revision_id = revision.id
            workflow.graph_hash = graph.sha256
            for artifact in (requirement_artifact, revision):
                await unit.audit.append(
                    workflow.id,
                    event_type="ARTIFACT_VERSION_CREATED",
                    actor_type="SYSTEM",
                    actor_id="workflow-api",
                    trace_id=trace_id,
                    artifact_refs=[
                        {
                            "id": str(artifact.id),
                            "version": artifact.version,
                            "sha256": artifact.content_sha256,
                        }
                    ],
                )
            if prepared.impact is not None:
                impact = await unit.artifacts.put(
                    workflow.id,
                    ArtifactInput(
                        logical_name="source-impact",
                        artifact_type="source_impact",
                        schema_version="1",
                        content={
                            "inspectedFiles": list(prepared.impact.inspected_files),
                            "affectedFiles": {
                                k: list(v) for k, v in prepared.impact.affected_files.items()
                            },
                        },
                    ),
                )
                await unit.lineage.add_relationship(
                    workflow.id,
                    parent_artifact_id=requirement_artifact.id,
                    child_artifact_id=impact.id,
                    relationship="DERIVED_FROM",
                )
                await unit.audit.append(
                    workflow.id,
                    event_type="SOURCE_INSPECTED",
                    actor_type="SYSTEM",
                    actor_id="source-impact-analyzer",
                    trace_id=trace_id,
                    artifact_refs=[
                        {
                            "id": str(impact.id),
                            "version": impact.version,
                            "sha256": impact.content_sha256,
                        }
                    ],
                )
            for definition in graph.stages:
                stage = await unit.stages.add_attempt(
                    workflow.id,
                    stage_name=definition.name,
                    generation=1,
                    attempt=1,
                    executor=definition.executor,
                )
                await unit.audit.append(
                    workflow.id,
                    event_type="STAGE_ATTEMPT_CREATED",
                    actor_type="SYSTEM",
                    actor_id="workflow-api",
                    stage_run_id=stage.id,
                    trace_id=trace_id,
                    after_state=stage.status.value,
                    payload={"stage_name": stage.stage_name},
                )
            return workflow.id

    @staticmethod
    def _graph_from_revision(revision: Artifact, graph_hash: str) -> WorkflowGraph:
        if canonical_content(revision.content)[1] != revision.content_sha256:
            raise ValueError("Persisted graph content hash is invalid")
        for variant in ("base", "conditional"):
            doc = revision.content[variant]
            graph = build_graph(
                doc["version"], tuple(StageDefinition.model_validate(s) for s in doc["stages"])
            )
            if graph.sha256 == graph_hash:
                return graph
        raise ValueError("Workflow graph hash does not match its persisted revision")

    async def graph_for(self, workflow_id: uuid.UUID) -> WorkflowGraph:
        async with UnitOfWork.open(self.factory) as unit:
            workflow = await unit.workflows.get(workflow_id)
            revision = await unit.session.get(Artifact, workflow.graph_revision_id)
            if revision is None or revision.workflow_id != workflow_id:
                raise ValueError("Persisted workflow graph revision is missing")
            return self._graph_from_revision(revision, workflow.graph_hash)

    async def status(self, workflow_id: uuid.UUID) -> WorkflowView:
        async with session_scope(self.factory) as session:
            # Domain mutations lock this row first. Keep generation, graph and stage
            # evidence consistent while answering a read, without writing any audit event.
            workflow = await session.scalar(
                select(WorkflowRun).where(WorkflowRun.id == workflow_id).with_for_update(read=True)
            )
            if workflow is None:
                raise KeyError(workflow_id)
            revision = await session.get(Artifact, workflow.graph_revision_id)
            if revision is None or revision.workflow_id != workflow_id:
                raise ValueError("Persisted workflow graph revision is missing")
            graph = self._graph_from_revision(revision, workflow.graph_hash)
            rows = list(
                await session.scalars(
                    select(StageRun)
                    .where(
                        StageRun.workflow_id == workflow_id,
                        StageRun.generation == workflow.generation,
                    )
                    .order_by(StageRun.stage_name, StageRun.attempt.desc())
                )
            )
            latest = {}
            for stage in rows:
                latest.setdefault(stage.stage_name, stage)
            decisions = StageDependencyResolver(graph).resolve(
                {name: stage.status for name, stage in latest.items()},
                generation=workflow.generation,
            )
            stages = []
            for name in graph.topological_order:
                stage = latest.get(name)
                unmet = list(decisions[name].unmet_dependencies)
                stages.append(
                    StageView(
                        stage_run_id=stage.id if stage else None,
                        stage_name=name,
                        status=stage.status if stage else StageStatus.BLOCKED,
                        generation=workflow.generation,
                        attempt=stage.attempt if stage else 0,
                        version=stage.version if stage else 0,
                        dependencies=list(graph.stage(name).dependencies),
                        unmet_dependencies=unmet,
                        blocked_reason=("Waiting for " + ", ".join(unmet)) if unmet else None,
                        error_message=stage.error_message if stage else None,
                        started_at=stage.started_at if stage else None,
                        completed_at=stage.completed_at if stage else None,
                    )
                )
            artifacts = list(
                await session.scalars(
                    select(Artifact)
                    .where(Artifact.workflow_id == workflow_id)
                    .order_by(Artifact.logical_name, Artifact.version.desc())
                )
            )
            current = {}
            for artifact in artifacts:
                current.setdefault(artifact.logical_name, artifact)
            lifecycles = {
                row.artifact_id: row
                for row in await session.scalars(
                    select(ArtifactLifecycle).where(ArtifactLifecycle.workflow_id == workflow_id)
                )
            }
            approvals = list(
                await session.scalars(
                    select(Approval)
                    .where(Approval.workflow_id == workflow_id, Approval.status == "PENDING")
                    .order_by(Approval.created_at)
                )
            )
            actions = [
                HumanAction(
                    kind="APPROVAL",
                    approval_id=a.id,
                    approval_type=a.approval_type,
                    artifact_id=a.artifact_id,
                    artifact_version=a.artifact_version,
                    artifact_hash=a.artifact_hash,
                )
                for a in approvals
            ]
            clarification = current.get("clarification")
            if workflow.status is WorkflowStatus.WAITING_FOR_CLARIFICATION and clarification:
                actions.append(
                    HumanAction(
                        kind="CLARIFICATION",
                        artifact_id=clarification.id,
                        artifact_version=clarification.version,
                        artifact_hash=clarification.content_sha256,
                        questions=clarification.content.get("questions", []),
                    )
                )
            blockers = [
                f"{s.stage_name}: {s.blocked_reason}"
                for s in stages
                if s.status is StageStatus.BLOCKED
            ]
            if workflow.stop_reason:
                blockers.insert(0, workflow.stop_reason)
            next_action = "Wait for scheduled stages to finish"
            if workflow.status is WorkflowStatus.WAITING_FOR_APPROVAL:
                next_action = "Review and decide the exact pending artifact version"
            elif workflow.status is WorkflowStatus.WAITING_FOR_CLARIFICATION:
                next_action = "Answer every pending clarification question"
            elif workflow.status is WorkflowStatus.SAFE_STOPPED:
                next_action = workflow.recommended_human_action or "Review the safe-stop reason"
            elif workflow.status in {
                WorkflowStatus.COMPLETED,
                WorkflowStatus.FAILED,
                WorkflowStatus.CANCELLED,
            }:
                next_action = "Inspect the terminal workflow evidence"
            state_version = await session.scalar(
                select(func.max(AuditEvent.sequence)).where(AuditEvent.workflow_id == workflow_id)
            )
            return WorkflowView(
                workflow_id=workflow.id,
                scenario_type=workflow.scenario_type,
                provider_mode=workflow.provider_mode,
                status=workflow.status,
                workflow_version=workflow.version,
                state_version=state_version or 0,
                generation=workflow.generation,
                requirement_version=workflow.requirement_version,
                graph_hash=graph.sha256,
                graph_version=graph.version,
                graph_revision_id=revision.id,
                stages=stages,
                blockers=blockers,
                pending_human_action=actions,
                artifacts=[
                    ArtifactView(
                        artifact_id=a.id,
                        logical_name=a.logical_name,
                        artifact_type=a.artifact_type,
                        version=a.version,
                        sha256=a.content_sha256,
                        status=lifecycles[a.id].status if a.id in lifecycles else "ACTIVE",
                    )
                    for a in current.values()
                ],
                next_action=next_action,
                last_successful_stage=workflow.last_successful_stage,
                stop_reason=workflow.stop_reason,
                created_at=workflow.created_at,
            )

    async def graph(self, workflow_id: uuid.UUID) -> GraphView:
        view = await self.status(workflow_id)
        async with session_scope(self.factory) as session:
            revision = await session.get(Artifact, view.graph_revision_id)
            graph = self._graph_from_revision(revision, view.graph_hash)
        by_name = {stage.stage_name: stage for stage in view.stages}
        nodes = []
        for name in graph.topological_order:
            definition = graph.stage(name)
            node = definition.model_dump(mode="json")
            node.update(by_name[name].model_dump(mode="json", by_alias=True))
            nodes.append(node)
        return GraphView(
            workflow_id=workflow_id,
            workflow_version=view.workflow_version,
            generation=view.generation,
            version=graph.version,
            graph_hash=graph.sha256,
            graph_revision_id=view.graph_revision_id,
            stages=nodes,
            current_stages=[
                s.stage_name
                for s in view.stages
                if s.status in {StageStatus.RUNNING, StageStatus.WAITING_APPROVAL}
            ],
            blocked_stages=[s.stage_name for s in view.stages if s.status is StageStatus.BLOCKED],
            ready_stages=[s.stage_name for s in view.stages if s.status is StageStatus.READY],
        )
