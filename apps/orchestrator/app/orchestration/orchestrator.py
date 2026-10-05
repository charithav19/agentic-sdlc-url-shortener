"""Sole transactional authority for workflow and stage status changes."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.contracts import AgentResult
from app.agents.output_schemas import RequirementOutput
from app.artifacts.candidate_refs import ArtifactStatus
from app.artifacts.impact import ArtifactImpactAnalyzer
from app.artifacts.lineage import ArtifactLineageService, LineageRelationship
from app.artifacts.schemas import ArtifactInput
from app.artifacts.store import ArtifactStore
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
from app.orchestration.claims import (
    ClaimUnavailableError,
    StageClaim,
    StageCompletion,
    StaleClaimError,
)
from app.orchestration.clarifications import (
    ClarificationSubmissionResult,
    RequirementAnalysisResult,
)
from app.orchestration.commands import TransitionContext
from app.orchestration.contracts import StageStatus, WorkflowStatus
from app.orchestration.dependencies import StageDependencyResolver
from app.orchestration.graph import WorkflowGraph
from app.orchestration.graph_loader import load_graph
from app.orchestration.readiness import ReadinessChange, StageSnapshot
from app.orchestration.replanning import ReplanResult, SelectiveReplanPlanner
from app.orchestration.state_authority import orchestrator_transition
from app.orchestration.state_machine import (
    InvalidTransitionError,
    StaleTransitionError,
    require_stage_transition,
    require_workflow_transition,
)
from app.persistence.models import (
    Approval,
    Artifact,
    ArtifactLifecycle,
    AuditEvent,
    CandidateReference,
    StageRun,
    WorkflowRun,
)
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

    async def update_requirement(
        self,
        workflow_id: uuid.UUID,
        *,
        requirement: str,
        update_id: uuid.UUID,
        context: TransitionContext,
        graph: WorkflowGraph | None = None,
    ) -> ReplanResult:
        """Version one requirement and prepare only its affected DAG closure."""

        if context.actor_type != "HUMAN":
            raise InvalidTransitionError("Requirement updates require a human actor")
        normalized = requirement.strip()
        if not normalized:
            raise ValueError("Requirement text is required")
        graph = graph or load_graph()
        planner = SelectiveReplanPlanner(graph)
        async with session_scope(self.session_factory) as session:
            workflow = await session.scalar(
                select(WorkflowRun).where(WorkflowRun.id == workflow_id).with_for_update()
            )
            if workflow is None:
                raise KeyError(f"Unknown workflow {workflow_id}")
            completed_replan = await session.scalar(
                select(AuditEvent)
                .where(
                    AuditEvent.workflow_id == workflow_id,
                    AuditEvent.event_type == "REPLAN_COMPLETED",
                    AuditEvent.payload["update_id"].as_string() == str(update_id),
                )
                .order_by(AuditEvent.sequence.desc())
                .limit(1)
            )
            if completed_replan is not None:
                payload = completed_replan.payload
                requirement_artifact_id = uuid.UUID(payload["requirement_artifact_id"])
                existing_requirement = await session.get(Artifact, requirement_artifact_id)
                if (
                    existing_requirement is None
                    or existing_requirement.content.get("requirement") != normalized
                ):
                    raise InvalidTransitionError(
                        "Requirement update ID was already used for different content"
                    )
                return ReplanResult(
                    workflow_id=workflow_id,
                    update_id=update_id,
                    workflow_status=WorkflowStatus(payload["workflow_status"]),
                    workflow_version=int(payload["workflow_version"]),
                    generation=int(payload["generation"]),
                    requirement_artifact_id=requirement_artifact_id,
                    requirement_version=int(payload["requirement_version"]),
                    superseded_requirement_artifact_id=uuid.UUID(
                        payload["superseded_requirement_artifact_id"]
                    ),
                    stale_artifact_ids=tuple(
                        uuid.UUID(value) for value in payload["affected_artifact_ids"]
                    ),
                    invalidated_approval_ids=tuple(
                        uuid.UUID(value) for value in payload["invalidated_approval_ids"]
                    ),
                    affected_stages=tuple(payload["affected_stages"]),
                    current_stage=payload["current_stage"],
                    architecture_approval_required=bool(payload["architecture_approval_required"]),
                )
            self._require_version(workflow.version, context.expected_version)
            if workflow.status not in {
                WorkflowStatus.RUNNING,
                WorkflowStatus.WAITING_FOR_CLARIFICATION,
                WorkflowStatus.WAITING_FOR_APPROVAL,
                WorkflowStatus.SAFE_STOPPED,
            }:
                raise InvalidTransitionError(
                    f"Cannot update requirements while workflow is {workflow.status.value}"
                )
            previous_requirement = await session.scalar(
                select(Artifact)
                .where(
                    Artifact.workflow_id == workflow_id,
                    Artifact.logical_name == "requirement",
                    Artifact.artifact_type == "requirement",
                )
                .order_by(Artifact.version.desc())
                .limit(1)
                .with_for_update()
            )
            if previous_requirement is None:
                raise KeyError("Workflow has no current requirement artifact")

            lineage = ArtifactLineageService(session)
            impact = await ArtifactImpactAnalyzer(lineage).downstream(
                workflow_id, previous_requirement.id
            )
            producer_stages = (
                list(
                    await session.scalars(
                        select(StageRun).where(StageRun.id.in_(impact.producer_stage_run_ids))
                    )
                )
                if impact.producer_stage_run_ids
                else []
            )
            affected_stages = planner.affected_stages(
                {stage.stage_name for stage in producer_stages}
            )
            audit = self.audit_store_factory(session)
            await audit.append(
                workflow_id,
                event_type="REPLAN_STARTED",
                actor_type=context.actor_type,
                actor_id=context.actor_id,
                trace_id=context.trace_id,
                artifact_refs=[self._artifact_ref(previous_requirement)],
                reason=context.reason or "Requirement changed",
                payload={
                    "update_id": str(update_id),
                    "from_requirement_version": previous_requirement.version,
                    "affected_artifact_ids": [str(value) for value in impact.artifact_ids],
                    "affected_stages": list(affected_stages),
                },
            )
            await self._transition_workflow_record(
                session,
                workflow,
                WorkflowStatus.REPLANNING,
                context,
                completion_verified=False,
            )

            current_requirement = await ArtifactStore(session).put(
                workflow_id,
                ArtifactInput(
                    logical_name="requirement",
                    artifact_type="requirement",
                    schema_version=previous_requirement.schema_version,
                    content={"requirement": normalized, "updateId": str(update_id)},
                    requirement_ids=list(previous_requirement.requirement_ids),
                    component_ids=list(previous_requirement.component_ids),
                ),
            )
            supersedes = await lineage.add_relationship(
                workflow_id,
                parent_artifact_id=previous_requirement.id,
                child_artifact_id=current_requirement.id,
                relationship=LineageRelationship.SUPERSEDES,
                requirement_ids=list(previous_requirement.requirement_ids),
                component_ids=list(previous_requirement.component_ids),
            )
            await audit.append(
                workflow_id,
                event_type="REQUIREMENT_UPDATED",
                actor_type=context.actor_type,
                actor_id=context.actor_id,
                trace_id=context.trace_id,
                artifact_refs=[
                    self._artifact_ref(previous_requirement),
                    self._artifact_ref(current_requirement),
                ],
                reason=context.reason,
                payload={
                    "update_id": str(update_id),
                    "lineage_edge_id": str(supersedes.id),
                    "relationship": LineageRelationship.SUPERSEDES.value,
                },
            )

            stale_artifact_ids = impact.artifact_ids
            for artifact_id in stale_artifact_ids:
                lifecycle = await session.scalar(
                    select(ArtifactLifecycle)
                    .where(ArtifactLifecycle.artifact_id == artifact_id)
                    .with_for_update()
                )
                if lifecycle is None:
                    lifecycle = ArtifactLifecycle(
                        artifact_id=artifact_id,
                        workflow_id=workflow_id,
                        status=ArtifactStatus.STALE.value,
                        active=False,
                        version=1,
                    )
                    session.add(lifecycle)
                elif lifecycle.status != ArtifactStatus.STALE.value or lifecycle.active:
                    lifecycle.status = ArtifactStatus.STALE.value
                    lifecycle.active = False
                    lifecycle.version += 1
                await audit.append(
                    workflow_id,
                    event_type="ARTIFACT_STALE",
                    actor_type="SYSTEM",
                    actor_id="selective-replanner",
                    trace_id=context.trace_id,
                    artifact_refs=[{"id": str(artifact_id)}],
                    reason="Descends from a superseded requirement",
                    payload={"update_id": str(update_id)},
                )

            stale_set = set(stale_artifact_ids)
            references = list(
                await session.scalars(
                    select(CandidateReference)
                    .where(CandidateReference.workflow_id == workflow_id)
                    .with_for_update()
                )
            )
            for reference in references:
                changed = False
                if reference.active_artifact_id in stale_set:
                    reference.active_artifact_id = None
                    changed = True
                if reference.approved_artifact_id in stale_set:
                    reference.approved_artifact_id = None
                    changed = True
                if changed:
                    reference.version += 1

            invalidated: list[Approval] = []
            if stale_artifact_ids:
                invalidated = list(
                    await session.scalars(
                        select(Approval)
                        .where(
                            Approval.workflow_id == workflow_id,
                            Approval.artifact_id.in_(stale_artifact_ids),
                            Approval.status.in_(
                                (ApprovalStatus.PENDING.value, ApprovalStatus.APPROVED.value)
                            ),
                        )
                        .with_for_update()
                    )
                )
            now = datetime.now(UTC)
            for approval in invalidated:
                approval.status = ApprovalStatus.INVALIDATED.value
                approval.reason = "Approved artifact depends on a superseded requirement"
                approval.decided_at = now
                await audit.append(
                    workflow_id,
                    event_type="APPROVAL_INVALIDATED",
                    actor_type="SYSTEM",
                    actor_id="selective-replanner",
                    trace_id=context.trace_id,
                    artifact_refs=[
                        {
                            "id": str(approval.artifact_id),
                            "version": approval.artifact_version,
                            "sha256": approval.artifact_hash,
                        }
                    ],
                    reason=approval.reason,
                    payload={
                        "approval_id": str(approval.id),
                        "update_id": str(update_id),
                    },
                )

            async def move_stage(stage: StageRun, target: StageStatus, event_type: str) -> None:
                previous = stage.status
                require_stage_transition(previous, target)
                with orchestrator_transition():
                    stage._status = target
                stage.version += 1
                if target in {StageStatus.RUNNING, StageStatus.FALLBACK_RUNNING}:
                    stage.started_at = stage.started_at or now
                if target in {
                    StageStatus.SUCCEEDED,
                    StageStatus.STALE,
                    StageStatus.CANCELLED,
                }:
                    stage.completed_at = now
                if target is StageStatus.STALE:
                    stage.lease_token = None
                    stage.claim_owner = None
                    stage.lease_expires_at = None
                await audit.append(
                    workflow_id,
                    event_type=event_type,
                    actor_type="SYSTEM",
                    actor_id="selective-replanner",
                    stage_run_id=stage.id,
                    trace_id=context.trace_id,
                    before_state=previous.value,
                    after_state=target.value,
                    reason="Requirement update changed stage inputs",
                    payload={
                        "update_id": str(update_id),
                        "stage_name": stage.stage_name,
                        "generation": stage.generation,
                        "attempt": stage.attempt,
                        "entity_version": stage.version,
                    },
                )

            old_generation = workflow.generation
            old_stages = list(
                await session.scalars(
                    select(StageRun)
                    .where(
                        StageRun.workflow_id == workflow_id,
                        StageRun.generation == old_generation,
                        StageRun.stage_name.in_(affected_stages),
                    )
                    .with_for_update()
                )
            )
            for stage in old_stages:
                if stage.status not in {
                    StageStatus.STALE,
                    StageStatus.ROLLED_BACK,
                    StageStatus.CANCELLED,
                    StageStatus.SAFE_STOPPED,
                }:
                    await move_stage(stage, StageStatus.STALE, "STAGE_STALE")

            workflow.generation += 1
            workflow.requirement_version = current_requirement.version
            workflow.graph_hash = graph.sha256
            workflow.last_successful_stage = "REQUIREMENT_ANALYSIS"
            new_generation = workflow.generation
            requirement_ref = self._artifact_ref(current_requirement)
            analysis = StageRun(
                workflow_id=workflow_id,
                stage_name="REQUIREMENT_ANALYSIS",
                generation=new_generation,
                attempt=1,
                _status=StageStatus.PENDING,
                executor=graph.stage("REQUIREMENT_ANALYSIS").executor,
                input_artifact_refs=[requirement_ref],
                result={"source": "human_requirement_update", "update_id": str(update_id)},
                version=1,
            )
            session.add(analysis)
            await session.flush()
            for status in (StageStatus.READY, StageStatus.RUNNING, StageStatus.SUCCEEDED):
                await move_stage(analysis, status, "STAGE_REPLAN_CREATED")

            for stage_name in affected_stages:
                definition = graph.stage(stage_name)
                stage = StageRun(
                    workflow_id=workflow_id,
                    stage_name=stage_name,
                    generation=new_generation,
                    attempt=1,
                    _status=StageStatus.PENDING,
                    executor=definition.executor,
                    input_artifact_refs=[requirement_ref],
                    version=1,
                )
                session.add(stage)
                await session.flush()
                target = (
                    StageStatus.READY if stage_name == "TASK_DECOMPOSITION" else StageStatus.BLOCKED
                )
                await move_stage(stage, target, "STAGE_REPLAN_CREATED")

            await audit.append(
                workflow_id,
                event_type="REPLAN_COMPLETED",
                actor_type=context.actor_type,
                actor_id=context.actor_id,
                trace_id=context.trace_id,
                artifact_refs=[self._artifact_ref(current_requirement)],
                reason="Selective replan generation prepared",
                payload={
                    "update_id": str(update_id),
                    "generation": new_generation,
                    "workflow_status": WorkflowStatus.RUNNING.value,
                    "workflow_version": workflow.version + 1,
                    "requirement_artifact_id": str(current_requirement.id),
                    "requirement_version": current_requirement.version,
                    "superseded_requirement_artifact_id": str(previous_requirement.id),
                    "current_stage": "TASK_DECOMPOSITION",
                    "affected_artifact_ids": [str(value) for value in stale_artifact_ids],
                    "invalidated_approval_ids": [str(item.id) for item in invalidated],
                    "affected_stages": list(affected_stages),
                    "architecture_approval_required": True,
                },
            )
            await self._transition_workflow_record(
                session,
                workflow,
                WorkflowStatus.RUNNING,
                TransitionContext(
                    actor_type=context.actor_type,
                    actor_id=context.actor_id,
                    trace_id=context.trace_id,
                    reason="Selective replan is ready for task decomposition",
                ),
                completion_verified=False,
            )
            return ReplanResult(
                workflow_id=workflow_id,
                update_id=update_id,
                workflow_status=workflow.status,
                workflow_version=workflow.version,
                generation=new_generation,
                requirement_artifact_id=current_requirement.id,
                requirement_version=current_requirement.version,
                superseded_requirement_artifact_id=previous_requirement.id,
                stale_artifact_ids=stale_artifact_ids,
                invalidated_approval_ids=tuple(item.id for item in invalidated),
                affected_stages=affected_stages,
                current_stage="TASK_DECOMPOSITION",
                architecture_approval_required=True,
            )

    async def record_requirement_analysis(
        self,
        workflow_id: uuid.UUID,
        *,
        requirement_artifact_id: uuid.UUID,
        result: AgentResult[RequirementOutput],
        context: TransitionContext,
    ) -> RequirementAnalysisResult:
        """Persist agent evidence and pause when its structured result is blocking."""

        if result.workflow_id != workflow_id:
            raise ValueError("Agent result belongs to another workflow")
        async with session_scope(self.session_factory) as session:
            workflow = await session.scalar(
                select(WorkflowRun).where(WorkflowRun.id == workflow_id).with_for_update()
            )
            stage = await session.scalar(
                select(StageRun)
                .where(
                    StageRun.id == result.stage_run_id,
                    StageRun.workflow_id == workflow_id,
                )
                .with_for_update()
            )
            requirement = await session.scalar(
                select(Artifact).where(
                    Artifact.id == requirement_artifact_id,
                    Artifact.workflow_id == workflow_id,
                    Artifact.artifact_type == "requirement",
                )
            )
            if workflow is None or stage is None or requirement is None:
                raise KeyError("Workflow, requirement, or analysis stage was not found")
            if (
                workflow.status is not WorkflowStatus.RUNNING
                or stage.stage_name != "REQUIREMENT_ANALYSIS"
                or stage.generation != workflow.generation
                or stage.status is not StageStatus.RUNNING
                or result.generation != workflow.generation
                or result.attempt != stage.attempt
            ):
                raise InvalidTransitionError("Requirement analysis result is not current")

            store = ArtifactStore(session)
            lineage = ArtifactLineageService(session)
            audit = self.audit_store_factory(session)
            analysis = await store.put(
                workflow_id,
                ArtifactInput(
                    logical_name="requirement-analysis",
                    artifact_type="requirement_analysis",
                    schema_version=result.schema_version,
                    content=result.output.model_dump(mode="json"),
                    producer_stage_run_id=stage.id,
                    requirement_ids=list(requirement.requirement_ids),
                    component_ids=list(requirement.component_ids),
                ),
            )
            await lineage.add_relationship(
                workflow_id,
                parent_artifact_id=requirement.id,
                child_artifact_id=analysis.id,
                relationship=LineageRelationship.DERIVED_FROM,
                requirement_ids=list(requirement.requirement_ids),
                component_ids=list(requirement.component_ids),
            )
            await self._move_stage_record(
                session,
                workflow,
                stage,
                StageStatus.SUCCEEDED,
                context,
                event_type="STAGE_CLAIM_COMPLETED",
                reason="Requirement analysis evidence persisted",
            )

            clarification: Artifact | None = None
            if result.output.blocking_ambiguity:
                clarification = await store.put(
                    workflow_id,
                    ArtifactInput(
                        logical_name="clarification",
                        artifact_type="clarification",
                        schema_version="1",
                        content={
                            "status": "PENDING",
                            "questions": result.output.clarifying_questions,
                            "answers": [],
                            "ambiguities": result.output.ambiguities,
                            "sourceAnalysisArtifactId": str(analysis.id),
                        },
                        producer_stage_run_id=stage.id,
                        requirement_ids=list(requirement.requirement_ids),
                        component_ids=list(requirement.component_ids),
                    ),
                )
                await lineage.add_relationship(
                    workflow_id,
                    parent_artifact_id=analysis.id,
                    child_artifact_id=clarification.id,
                    relationship=LineageRelationship.DERIVED_FROM,
                    requirement_ids=list(requirement.requirement_ids),
                    component_ids=list(requirement.component_ids),
                )
                clarification_stage = StageRun(
                    workflow_id=workflow_id,
                    stage_name="CLARIFICATION",
                    generation=workflow.generation,
                    attempt=1,
                    _status=StageStatus.PENDING,
                    executor="clarification",
                    input_artifact_refs=[self._artifact_ref(clarification)],
                    version=1,
                )
                session.add(clarification_stage)
                await session.flush()
                for target in (
                    StageStatus.READY,
                    StageStatus.RUNNING,
                    StageStatus.WAITING_APPROVAL,
                ):
                    await self._move_stage_record(
                        session,
                        workflow,
                        clarification_stage,
                        target,
                        context,
                        event_type="STAGE_CLARIFICATION_CHANGED",
                        reason="Blocking ambiguity requires human clarification",
                    )
                workflow.graph_hash = load_graph(blocking_ambiguity=True).sha256
                await audit.append(
                    workflow_id,
                    event_type="CLARIFICATION_REQUESTED",
                    actor_type="SYSTEM",
                    actor_id="requirement-analysis",
                    stage_run_id=clarification_stage.id,
                    trace_id=context.trace_id,
                    artifact_refs=[self._artifact_ref(clarification)],
                    reason="RequirementAgent reported blocking ambiguity",
                    payload={
                        "questions": result.output.clarifying_questions,
                        "analysis_artifact_id": str(analysis.id),
                        "provider": result.provider,
                        "model": result.model,
                        "context_sha256": result.context_sha256,
                    },
                )
                await self._transition_workflow_record(
                    session,
                    workflow,
                    WorkflowStatus.WAITING_FOR_CLARIFICATION,
                    TransitionContext(
                        actor_type="SYSTEM",
                        actor_id="requirement-analysis",
                        trace_id=context.trace_id,
                        reason="Blocking requirement ambiguity",
                    ),
                    completion_verified=False,
                )
            return RequirementAnalysisResult(
                workflow_id=workflow_id,
                workflow_status=workflow.status,
                workflow_version=workflow.version,
                analysis_artifact_id=analysis.id,
                analysis_artifact_version=analysis.version,
                clarification_artifact_id=clarification.id if clarification else None,
                clarification_artifact_version=clarification.version if clarification else None,
                blocking_ambiguity=result.output.blocking_ambiguity,
                questions=tuple(result.output.clarifying_questions),
            )

    async def submit_clarification(
        self,
        workflow_id: uuid.UUID,
        *,
        clarification_artifact_id: uuid.UUID,
        clarification_artifact_version: int,
        answers: dict[str, str],
        context: TransitionContext,
    ) -> ClarificationSubmissionResult:
        """Version human answers and restart requirement analysis in a new generation."""

        if context.actor_type != "HUMAN":
            raise InvalidTransitionError("Clarifications require a human actor")
        normalized_answers = {
            question.strip(): answer.strip() for question, answer in answers.items()
        }
        if not normalized_answers or any(
            not key or not value for key, value in normalized_answers.items()
        ):
            raise ValueError("Every clarification question requires a nonblank answer")
        async with session_scope(self.session_factory) as session:
            workflow = await session.scalar(
                select(WorkflowRun).where(WorkflowRun.id == workflow_id).with_for_update()
            )
            if workflow is None:
                raise KeyError(f"Unknown workflow {workflow_id}")
            self._require_version(workflow.version, context.expected_version)
            if workflow.status is not WorkflowStatus.WAITING_FOR_CLARIFICATION:
                raise InvalidTransitionError("Workflow is not waiting for clarification")
            clarification = await session.scalar(
                select(Artifact)
                .where(
                    Artifact.id == clarification_artifact_id,
                    Artifact.workflow_id == workflow_id,
                    Artifact.version == clarification_artifact_version,
                    Artifact.logical_name == "clarification",
                    Artifact.artifact_type == "clarification",
                )
                .with_for_update()
            )
            if clarification is None or clarification.content.get("status") != "PENDING":
                raise InvalidTransitionError(
                    "Clarification artifact is missing or no longer pending"
                )
            latest_clarification_version = await session.scalar(
                select(func.max(Artifact.version)).where(
                    Artifact.workflow_id == workflow_id,
                    Artifact.logical_name == "clarification",
                )
            )
            if latest_clarification_version != clarification.version:
                raise InvalidTransitionError("Clarification artifact is stale")
            questions = tuple(str(value) for value in clarification.content.get("questions", []))
            if set(normalized_answers) != set(questions):
                raise ValueError("Answers must match every pending clarification question exactly")
            requirement = await session.scalar(
                select(Artifact)
                .where(
                    Artifact.workflow_id == workflow_id,
                    Artifact.logical_name == "requirement",
                    Artifact.artifact_type == "requirement",
                )
                .order_by(Artifact.version.desc())
                .limit(1)
                .with_for_update()
            )
            clarification_stage = await session.scalar(
                select(StageRun)
                .where(
                    StageRun.workflow_id == workflow_id,
                    StageRun.generation == workflow.generation,
                    StageRun.stage_name == "CLARIFICATION",
                    StageRun._status == StageStatus.WAITING_APPROVAL,
                )
                .with_for_update()
            )
            if requirement is None or clarification_stage is None:
                raise InvalidTransitionError("Clarification context is incomplete")

            audit = self.audit_store_factory(session)
            store = ArtifactStore(session)
            lineage = ArtifactLineageService(session)
            await audit.append(
                workflow_id,
                event_type="REPLAN_STARTED",
                actor_type=context.actor_type,
                actor_id=context.actor_id,
                trace_id=context.trace_id,
                artifact_refs=[self._artifact_ref(clarification)],
                reason=context.reason or "Clarification submitted",
                payload={"from_generation": workflow.generation},
            )
            await self._transition_workflow_record(
                session,
                workflow,
                WorkflowStatus.REPLANNING,
                context,
                completion_verified=False,
            )
            answered = await store.put(
                workflow_id,
                ArtifactInput(
                    logical_name="clarification",
                    artifact_type="clarification",
                    schema_version=clarification.schema_version,
                    content={
                        **clarification.content,
                        "status": "ANSWERED",
                        "answers": [
                            {"question": question, "answer": normalized_answers[question]}
                            for question in questions
                        ],
                    },
                    requirement_ids=list(clarification.requirement_ids),
                    component_ids=list(clarification.component_ids),
                ),
            )
            await lineage.add_relationship(
                workflow_id,
                parent_artifact_id=clarification.id,
                child_artifact_id=answered.id,
                relationship=LineageRelationship.SUPERSEDES,
                requirement_ids=list(clarification.requirement_ids),
                component_ids=list(clarification.component_ids),
            )
            revised_requirement = await store.put(
                workflow_id,
                ArtifactInput(
                    logical_name="requirement",
                    artifact_type="requirement",
                    schema_version=requirement.schema_version,
                    content={
                        "requirement": requirement.content.get("requirement", ""),
                        "clarifications": answered.content["answers"],
                        "sourceClarificationArtifactId": str(answered.id),
                    },
                    requirement_ids=list(requirement.requirement_ids),
                    component_ids=list(requirement.component_ids),
                ),
            )
            await lineage.add_relationship(
                workflow_id,
                parent_artifact_id=requirement.id,
                child_artifact_id=revised_requirement.id,
                relationship=LineageRelationship.SUPERSEDES,
                requirement_ids=list(requirement.requirement_ids),
                component_ids=list(requirement.component_ids),
            )
            await lineage.add_relationship(
                workflow_id,
                parent_artifact_id=answered.id,
                child_artifact_id=revised_requirement.id,
                relationship=LineageRelationship.DERIVED_FROM,
                requirement_ids=list(requirement.requirement_ids),
                component_ids=list(requirement.component_ids),
            )
            await self._move_stage_record(
                session,
                workflow,
                clarification_stage,
                StageStatus.SUCCEEDED,
                context,
                event_type="STAGE_CLARIFICATION_CHANGED",
                reason="All clarification questions answered",
            )

            old_generation = workflow.generation
            old_stages = list(
                await session.scalars(
                    select(StageRun)
                    .where(
                        StageRun.workflow_id == workflow_id,
                        StageRun.generation == old_generation,
                        StageRun.stage_name != "CLARIFICATION",
                    )
                    .with_for_update()
                )
            )
            for old_stage in old_stages:
                if old_stage.status not in {
                    StageStatus.STALE,
                    StageStatus.CANCELLED,
                    StageStatus.ROLLED_BACK,
                    StageStatus.SAFE_STOPPED,
                }:
                    await self._move_stage_record(
                        session,
                        workflow,
                        old_stage,
                        StageStatus.STALE,
                        context,
                        event_type="STAGE_STALE",
                        reason="Clarification created a new requirement generation",
                    )

            prior_analysis = await session.scalar(
                select(Artifact)
                .where(
                    Artifact.workflow_id == workflow_id,
                    Artifact.logical_name == "requirement-analysis",
                )
                .order_by(Artifact.version.desc())
                .limit(1)
            )
            for stale_artifact in (clarification, prior_analysis):
                if stale_artifact is None:
                    continue
                lifecycle = await session.get(ArtifactLifecycle, stale_artifact.id)
                if lifecycle is None:
                    session.add(
                        ArtifactLifecycle(
                            artifact_id=stale_artifact.id,
                            workflow_id=workflow_id,
                            status=ArtifactStatus.STALE.value,
                            active=False,
                            version=1,
                        )
                    )
                else:
                    lifecycle.status = ArtifactStatus.STALE.value
                    lifecycle.active = False
                    lifecycle.version += 1

            workflow.generation += 1
            workflow.requirement_version = revised_requirement.version
            workflow.graph_hash = load_graph().sha256
            reused_intake_stage = StageRun(
                workflow_id=workflow_id,
                stage_name="INTAKE",
                generation=workflow.generation,
                attempt=1,
                _status=StageStatus.PENDING,
                executor="intake",
                input_artifact_refs=[self._artifact_ref(revised_requirement)],
                result={
                    "source": "preserved_intake",
                    "clarification_artifact_id": str(answered.id),
                },
                version=1,
            )
            session.add(reused_intake_stage)
            await session.flush()
            for target in (StageStatus.READY, StageStatus.RUNNING, StageStatus.SUCCEEDED):
                await self._move_stage_record(
                    session,
                    workflow,
                    reused_intake_stage,
                    target,
                    context,
                    event_type="STAGE_REPLAN_CREATED",
                    reason="Preserve validated intake for clarified requirement",
                )
            new_analysis_stage = StageRun(
                workflow_id=workflow_id,
                stage_name="REQUIREMENT_ANALYSIS",
                generation=workflow.generation,
                attempt=1,
                _status=StageStatus.PENDING,
                executor="requirements_specialist",
                input_artifact_refs=[self._artifact_ref(revised_requirement)],
                version=1,
            )
            session.add(new_analysis_stage)
            await session.flush()
            await self._move_stage_record(
                session,
                workflow,
                new_analysis_stage,
                StageStatus.READY,
                context,
                event_type="STAGE_REPLAN_CREATED",
                reason="Clarified requirement requires fresh analysis",
            )
            await audit.append(
                workflow_id,
                event_type="CLARIFICATION_SUBMITTED",
                actor_type=context.actor_type,
                actor_id=context.actor_id,
                stage_run_id=clarification_stage.id,
                trace_id=context.trace_id,
                artifact_refs=[
                    self._artifact_ref(answered),
                    self._artifact_ref(revised_requirement),
                ],
                reason=context.reason,
                payload={"question_count": len(questions), "generation": workflow.generation},
            )
            await audit.append(
                workflow_id,
                event_type="REPLAN_COMPLETED",
                actor_type=context.actor_type,
                actor_id=context.actor_id,
                trace_id=context.trace_id,
                artifact_refs=[self._artifact_ref(revised_requirement)],
                reason="Fresh requirement analysis is ready",
                payload={
                    "generation": workflow.generation,
                    "current_stage": "REQUIREMENT_ANALYSIS",
                },
            )
            await self._transition_workflow_record(
                session,
                workflow,
                WorkflowStatus.RUNNING,
                TransitionContext(
                    actor_type=context.actor_type,
                    actor_id=context.actor_id,
                    trace_id=context.trace_id,
                    reason="Clarification accepted; rerun requirement analysis",
                ),
                completion_verified=False,
            )
            return ClarificationSubmissionResult(
                workflow_id=workflow_id,
                workflow_status=workflow.status,
                workflow_version=workflow.version,
                generation=workflow.generation,
                clarification_artifact_id=answered.id,
                clarification_artifact_version=answered.version,
                requirement_artifact_id=revised_requirement.id,
                requirement_version=revised_requirement.version,
                requirement_analysis_stage_run_id=new_analysis_stage.id,
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
            if target in {StageStatus.RUNNING, StageStatus.FALLBACK_RUNNING} and (
                workflow.status is not WorkflowStatus.RUNNING
            ):
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
            if target in {StageStatus.RUNNING, StageStatus.FALLBACK_RUNNING} and (
                stage.started_at is None
            ):
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

    async def claim_stage(
        self,
        stage_run_id: uuid.UUID,
        *,
        owner: str,
        lease_seconds: int,
        context: TransitionContext,
    ) -> StageClaim:
        """Atomically claim one READY attempt and transition it to RUNNING."""

        if not owner.strip():
            raise ValueError("Claim owner is required")
        if lease_seconds < 1:
            raise ValueError("Claim lease must be positive")
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
            stage = await session.scalar(
                select(StageRun).where(StageRun.id == stage_run_id).with_for_update()
            )
            if workflow is None or stage is None:
                raise KeyError(f"Unknown stage run {stage_run_id}")
            if workflow.status is not WorkflowStatus.RUNNING:
                raise ClaimUnavailableError(
                    f"Workflow is {workflow.status.value}; stage claims are disabled"
                )
            if stage.generation != workflow.generation:
                raise ClaimUnavailableError("Stage attempt is not in the current generation")
            if stage.status is not StageStatus.READY or stage.lease_token is not None:
                raise ClaimUnavailableError(f"Stage {stage.stage_name} is not available for claim")
            target = (
                StageStatus.FALLBACK_RUNNING
                if stage.execution_mode == "FALLBACK"
                else StageStatus.RUNNING
            )
            require_stage_transition(stage.status, target)
            now = datetime.now(UTC)
            token = uuid.uuid4()
            expires_at = now + timedelta(seconds=lease_seconds)
            previous = stage.status
            with orchestrator_transition():
                stage._status = target
            stage.version += 1
            stage.started_at = stage.started_at or now
            stage.lease_token = token
            stage.claim_owner = owner
            stage.lease_expires_at = expires_at
            await self.audit_store_factory(session).append(
                workflow.id,
                event_type="STAGE_CLAIMED",
                actor_type=context.actor_type,
                actor_id=context.actor_id,
                stage_run_id=stage.id,
                trace_id=context.trace_id,
                before_state=previous.value,
                after_state=target.value,
                payload={
                    "entity_version": stage.version,
                    "stage_name": stage.stage_name,
                    "generation": stage.generation,
                    "attempt": stage.attempt,
                    "execution_mode": stage.execution_mode,
                    "claim_owner": owner,
                    "claim_token": str(token),
                    "lease_expires_at": expires_at.isoformat(),
                },
            )
            return StageClaim(
                stage_run_id=stage.id,
                workflow_id=workflow.id,
                stage_name=stage.stage_name,
                executor=stage.executor,
                generation=stage.generation,
                attempt=stage.attempt,
                execution_mode=stage.execution_mode,
                token=token,
                owner=owner,
                lease_expires_at=expires_at,
            )

    async def synchronize_stage_readiness(
        self,
        workflow_id: uuid.UUID,
        graph: WorkflowGraph,
        context: TransitionContext,
    ) -> tuple[ReadinessChange, ...]:
        """Atomically apply dependency-derived READY/BLOCKED changes."""

        async with session_scope(self.session_factory) as session:
            workflow = await session.scalar(
                select(WorkflowRun).where(WorkflowRun.id == workflow_id).with_for_update()
            )
            if workflow is None:
                raise KeyError(f"Unknown workflow {workflow_id}")
            if workflow.status is not WorkflowStatus.RUNNING:
                return ()
            rows = list(
                await session.scalars(
                    select(StageRun)
                    .where(
                        StageRun.workflow_id == workflow_id,
                        StageRun.generation == workflow.generation,
                    )
                    .order_by(StageRun.stage_name, StageRun.attempt.desc())
                    .with_for_update()
                )
            )
            latest: dict[str, StageRun] = {}
            for stage in rows:
                latest.setdefault(stage.stage_name, stage)
            snapshots = {
                name: StageSnapshot(status=stage.status, generation=stage.generation)
                for name, stage in latest.items()
            }
            decisions = StageDependencyResolver(graph).resolve(
                snapshots, generation=workflow.generation
            )
            changes: list[ReadinessChange] = []
            for stage_name in graph.topological_order:
                stage = latest.get(stage_name)
                if stage is None:
                    continue
                decision = decisions[stage_name]
                if (
                    stage.retry_due_at is not None
                    and stage.retry_due_at > datetime.now(UTC)
                    and decision.status is StageStatus.READY
                ):
                    continue
                if decision.status is stage.status:
                    continue
                previous = stage.status
                require_stage_transition(previous, decision.status)
                with orchestrator_transition():
                    stage._status = decision.status
                stage.version += 1
                await self.audit_store_factory(session).append(
                    workflow_id,
                    event_type="STAGE_READINESS_CHANGED",
                    actor_type=context.actor_type,
                    actor_id=context.actor_id,
                    stage_run_id=stage.id,
                    trace_id=context.trace_id,
                    before_state=previous.value,
                    after_state=decision.status.value,
                    payload={
                        "entity_version": stage.version,
                        "stage_name": stage.stage_name,
                        "generation": stage.generation,
                        "attempt": stage.attempt,
                        "unmet_dependencies": list(decision.unmet_dependencies),
                    },
                )
                changes.append(
                    ReadinessChange(
                        stage_run_id=stage.id,
                        stage_name=stage.stage_name,
                        previous_status=previous,
                        current_status=decision.status,
                        unmet_dependencies=decision.unmet_dependencies,
                    )
                )
            return tuple(changes)

    async def complete_stage_claim(
        self,
        claim: StageClaim,
        *,
        succeeded: bool,
        result: dict | None,
        error_message: str | None,
        failure_code: str | None = None,
        recommended_action: str | None = None,
        context: TransitionContext,
    ) -> StageCompletion:
        """Commit a claimed result only when its exact token remains current."""

        async with session_scope(self.session_factory) as session:
            workflow = await session.scalar(
                select(WorkflowRun).where(WorkflowRun.id == claim.workflow_id).with_for_update()
            )
            stage = await session.scalar(
                select(StageRun).where(StageRun.id == claim.stage_run_id).with_for_update()
            )
            if workflow is None or stage is None:
                raise StaleClaimError("Claimed workflow or stage no longer exists")
            now = datetime.now(UTC)
            if (
                workflow.status is not WorkflowStatus.RUNNING
                or workflow.generation != claim.generation
                or stage.generation != claim.generation
                or stage.status
                is not (
                    StageStatus.FALLBACK_RUNNING
                    if claim.execution_mode == "FALLBACK"
                    else StageStatus.RUNNING
                )
                or stage.lease_token != claim.token
                or stage.claim_owner != claim.owner
                or stage.lease_expires_at is None
                or stage.lease_expires_at <= now
            ):
                raise StaleClaimError("Stage claim token is stale or expired")
            target = StageStatus.SUCCEEDED if succeeded else StageStatus.FAILED
            require_stage_transition(stage.status, target)
            previous = stage.status
            with orchestrator_transition():
                stage._status = target
            stage.version += 1
            stage.completed_at = now
            stage.result = result
            stage.error_message = error_message
            stage.failure_code = failure_code
            stage.recommended_action = recommended_action
            stage.lease_token = None
            stage.claim_owner = None
            stage.lease_expires_at = None
            if succeeded:
                workflow.last_successful_stage = stage.stage_name
            await self.audit_store_factory(session).append(
                workflow.id,
                event_type="STAGE_CLAIM_COMPLETED" if succeeded else "STAGE_CLAIM_FAILED",
                actor_type=context.actor_type,
                actor_id=context.actor_id,
                stage_run_id=stage.id,
                trace_id=context.trace_id,
                before_state=previous.value,
                after_state=target.value,
                reason=error_message,
                payload={
                    "entity_version": stage.version,
                    "stage_name": stage.stage_name,
                    "generation": stage.generation,
                    "attempt": stage.attempt,
                    "execution_mode": stage.execution_mode,
                    "failure_code": failure_code,
                    "claim_owner": claim.owner,
                    "claim_token": str(claim.token),
                },
            )
            return StageCompletion(
                stage_run_id=stage.id,
                stage_name=stage.stage_name,
                succeeded=succeeded,
                version=stage.version,
            )

    async def schedule_retry(
        self,
        stage_run_id: uuid.UUID,
        *,
        due_at: datetime,
        context: TransitionContext,
    ) -> uuid.UUID:
        """Close one failed attempt and create its distinct durable successor."""

        async with session_scope(self.session_factory) as session:
            stage = await session.scalar(
                select(StageRun).where(StageRun.id == stage_run_id).with_for_update()
            )
            if stage is None:
                raise KeyError(f"Unknown stage run {stage_run_id}")
            workflow = await session.scalar(
                select(WorkflowRun).where(WorkflowRun.id == stage.workflow_id).with_for_update()
            )
            if workflow is None or workflow.status is not WorkflowStatus.RUNNING:
                raise InvalidTransitionError("Retry requires a running workflow")
            newer = await session.scalar(
                select(StageRun)
                .where(
                    StageRun.workflow_id == stage.workflow_id,
                    StageRun.generation == stage.generation,
                    StageRun.stage_name == stage.stage_name,
                    StageRun.attempt > stage.attempt,
                )
                .order_by(StageRun.attempt.desc())
                .limit(1)
                .with_for_update()
            )
            if newer is not None:
                return newer.id
            if stage.status is not StageStatus.FAILED or stage.execution_mode != "PRIMARY":
                raise InvalidTransitionError("Only a failed primary attempt can be retried")
            require_stage_transition(stage.status, StageStatus.RETRY_PENDING)
            previous = stage.status
            with orchestrator_transition():
                stage._status = StageStatus.RETRY_PENDING
            stage.version += 1
            stage.retry_due_at = due_at
            successor = StageRun(
                workflow_id=stage.workflow_id,
                stage_name=stage.stage_name,
                generation=stage.generation,
                attempt=stage.attempt + 1,
                _status=StageStatus.PENDING,
                executor=stage.executor,
                input_artifact_refs=stage.input_artifact_refs,
                retry_due_at=due_at,
                execution_mode="PRIMARY",
                version=1,
            )
            session.add(successor)
            await session.flush()
            await self.audit_store_factory(session).append(
                workflow.id,
                event_type="STAGE_RETRY_SCHEDULED",
                actor_type=context.actor_type,
                actor_id=context.actor_id,
                stage_run_id=stage.id,
                trace_id=context.trace_id,
                before_state=previous.value,
                after_state=StageStatus.RETRY_PENDING.value,
                reason=stage.error_message,
                payload={
                    "failure_code": stage.failure_code,
                    "completed_attempt": stage.attempt,
                    "next_attempt": successor.attempt,
                    "next_stage_run_id": str(successor.id),
                    "retry_due_at": due_at.isoformat(),
                },
            )
            return successor.id

    async def schedule_fallback(
        self,
        stage_run_id: uuid.UUID,
        *,
        fallback_executor: str,
        context: TransitionContext,
    ) -> uuid.UUID:
        """Create a separately claimed fallback attempt with source provenance."""

        async with session_scope(self.session_factory) as session:
            stage = await session.scalar(
                select(StageRun).where(StageRun.id == stage_run_id).with_for_update()
            )
            if stage is None:
                raise KeyError(f"Unknown stage run {stage_run_id}")
            workflow = await session.scalar(
                select(WorkflowRun).where(WorkflowRun.id == stage.workflow_id).with_for_update()
            )
            if workflow is None or workflow.status is not WorkflowStatus.RUNNING:
                raise InvalidTransitionError("Fallback requires a running workflow")
            existing = await session.scalar(
                select(StageRun)
                .where(StageRun.fallback_source_stage_run_id == stage.id)
                .with_for_update()
            )
            if existing is not None:
                return existing.id
            if stage.status is not StageStatus.FAILED or stage.execution_mode != "PRIMARY":
                raise InvalidTransitionError(
                    "Fallback requires an exhausted failed primary attempt"
                )
            fallback = StageRun(
                workflow_id=stage.workflow_id,
                stage_name=stage.stage_name,
                generation=stage.generation,
                attempt=stage.attempt + 1,
                _status=StageStatus.PENDING,
                executor=fallback_executor,
                input_artifact_refs=stage.input_artifact_refs,
                execution_mode="FALLBACK",
                fallback_source_stage_run_id=stage.id,
                version=1,
            )
            session.add(fallback)
            await session.flush()
            await self.audit_store_factory(session).append(
                workflow.id,
                event_type="STAGE_FALLBACK_SCHEDULED",
                actor_type=context.actor_type,
                actor_id=context.actor_id,
                stage_run_id=fallback.id,
                trace_id=context.trace_id,
                after_state=StageStatus.PENDING.value,
                reason=stage.error_message,
                payload={
                    "failure_code": stage.failure_code,
                    "fallback_executor": fallback_executor,
                    "source_stage_run_id": str(stage.id),
                    "source_attempt": stage.attempt,
                    "fallback_attempt": fallback.attempt,
                },
            )
            return fallback.id

    async def safe_stop(
        self,
        stage_run_id: uuid.UUID,
        *,
        failure_reason: str,
        failure_code: str,
        recommended_action: str,
        context: TransitionContext,
    ) -> None:
        """Atomically stop the failing stage and workflow with actionable evidence."""

        async with session_scope(self.session_factory) as session:
            stage = await session.scalar(
                select(StageRun).where(StageRun.id == stage_run_id).with_for_update()
            )
            if stage is None:
                raise KeyError(f"Unknown stage run {stage_run_id}")
            workflow = await session.scalar(
                select(WorkflowRun).where(WorkflowRun.id == stage.workflow_id).with_for_update()
            )
            if workflow is None:
                raise KeyError(f"Unknown workflow {stage.workflow_id}")
            if (
                stage.status is StageStatus.SAFE_STOPPED
                and workflow.status is WorkflowStatus.SAFE_STOPPED
            ):
                return
            require_stage_transition(stage.status, StageStatus.SAFE_STOPPED)
            if workflow.status not in {WorkflowStatus.RUNNING, WorkflowStatus.SAFE_STOPPED}:
                raise InvalidTransitionError(
                    f"Cannot safe-stop a stage while workflow is {workflow.status.value}"
                )
            previous_stage = stage.status
            with orchestrator_transition():
                stage._status = StageStatus.SAFE_STOPPED
            stage.version += 1
            stage.completed_at = datetime.now(UTC)
            stage.error_message = failure_reason
            stage.failure_code = failure_code
            stage.recommended_action = recommended_action
            await self.audit_store_factory(session).append(
                workflow.id,
                event_type="STAGE_SAFE_STOPPED",
                actor_type=context.actor_type,
                actor_id=context.actor_id,
                stage_run_id=stage.id,
                trace_id=context.trace_id,
                before_state=previous_stage.value,
                after_state=StageStatus.SAFE_STOPPED.value,
                reason=failure_reason,
                payload={
                    "failure_code": failure_code,
                    "recommended_human_action": recommended_action,
                    "attempt": stage.attempt,
                },
            )
            if workflow.status is WorkflowStatus.RUNNING:
                workflow.stop_reason = failure_reason
                workflow.recommended_human_action = recommended_action
                await self._transition_workflow_record(
                    session,
                    workflow,
                    WorkflowStatus.SAFE_STOPPED,
                    TransitionContext(
                        actor_type=context.actor_type,
                        actor_id=context.actor_id,
                        reason=failure_reason,
                        trace_id=context.trace_id,
                    ),
                    completion_verified=False,
                )

    async def resume_safe_stopped(
        self,
        workflow_id: uuid.UUID,
        *,
        stage_run_id: uuid.UUID,
        resolution: str,
        context: TransitionContext,
    ) -> TransitionResult:
        """Resume only an exact latest stopped attempt after a human records resolution."""

        if context.actor_type != "HUMAN" or not resolution.strip():
            raise InvalidTransitionError("Recovery requires a human resolution")
        async with session_scope(self.session_factory) as session:
            workflow = await session.scalar(
                select(WorkflowRun).where(WorkflowRun.id == workflow_id).with_for_update()
            )
            stage = await session.scalar(
                select(StageRun)
                .where(StageRun.id == stage_run_id, StageRun.workflow_id == workflow_id)
                .with_for_update()
            )
            if workflow is None or stage is None:
                raise KeyError("Workflow or stopped stage was not found")
            self._require_version(workflow.version, context.expected_version)
            latest_attempt = await session.scalar(
                select(func.max(StageRun.attempt)).where(
                    StageRun.workflow_id == workflow_id,
                    StageRun.generation == workflow.generation,
                    StageRun.stage_name == stage.stage_name,
                )
            )
            if (
                workflow.status is not WorkflowStatus.SAFE_STOPPED
                or stage.status is not StageStatus.SAFE_STOPPED
                or latest_attempt != stage.attempt
            ):
                raise InvalidTransitionError("Only the latest safe-stopped attempt can resume")
            await self._validate_recovery_inputs(session, workflow, stage)
            successor = StageRun(
                workflow_id=stage.workflow_id,
                stage_name=stage.stage_name,
                generation=stage.generation,
                attempt=stage.attempt + 1,
                _status=StageStatus.PENDING,
                executor=stage.executor,
                input_artifact_refs=stage.input_artifact_refs,
                execution_mode=stage.execution_mode,
                fallback_source_stage_run_id=stage.fallback_source_stage_run_id,
                version=1,
            )
            session.add(successor)
            await session.flush()
            await self.audit_store_factory(session).append(
                workflow.id,
                event_type="STAGE_RECOVERY_APPROVED",
                actor_type="HUMAN",
                actor_id=context.actor_id,
                stage_run_id=successor.id,
                trace_id=context.trace_id,
                before_state=stage.status.value,
                after_state=StageStatus.PENDING.value,
                reason=resolution,
                payload={
                    "failure_code": stage.failure_code,
                    "stopped_stage_run_id": str(stage.id),
                    "stopped_attempt": stage.attempt,
                    "recovery_stage_run_id": str(successor.id),
                    "recovery_attempt": successor.attempt,
                },
            )
            return await self._transition_workflow_record(
                session,
                workflow,
                WorkflowStatus.RUNNING,
                TransitionContext(
                    actor_type="HUMAN",
                    actor_id=context.actor_id,
                    reason=resolution,
                    trace_id=context.trace_id,
                ),
                completion_verified=False,
            )

    @staticmethod
    async def _validate_recovery_inputs(
        session: AsyncSession, workflow: WorkflowRun, stage: StageRun
    ) -> None:
        """Reject recovery when an exact input disappeared or has a newer version."""

        for ref in stage.input_artifact_refs:
            try:
                artifact_id = uuid.UUID(str(ref["id"]))
                version = int(ref["version"])
                digest = str(ref["sha256"])
            except (KeyError, TypeError, ValueError) as error:
                raise InvalidTransitionError("Recovery input lineage is malformed") from error
            artifact = await session.scalar(
                select(Artifact).where(
                    Artifact.id == artifact_id,
                    Artifact.workflow_id == workflow.id,
                    Artifact.version == version,
                    Artifact.content_sha256 == digest,
                )
            )
            if artifact is None:
                raise InvalidTransitionError("Recovery input artifact is missing or corrupt")
            newer = await session.scalar(
                select(func.count())
                .select_from(Artifact)
                .where(
                    Artifact.workflow_id == workflow.id,
                    Artifact.logical_name == artifact.logical_name,
                    Artifact.version > artifact.version,
                )
            )
            if newer:
                raise InvalidTransitionError("Recovery input artifact is no longer current")

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

    async def _move_stage_record(
        self,
        session: AsyncSession,
        workflow: WorkflowRun,
        stage: StageRun,
        target: StageStatus,
        context: TransitionContext,
        *,
        event_type: str,
        reason: str,
    ) -> None:
        previous = stage.status
        require_stage_transition(previous, target)
        now = datetime.now(UTC)
        with orchestrator_transition():
            stage._status = target
        stage.version += 1
        if target in {StageStatus.RUNNING, StageStatus.FALLBACK_RUNNING}:
            stage.started_at = stage.started_at or now
        if target in {
            StageStatus.SUCCEEDED,
            StageStatus.FAILED,
            StageStatus.ROLLED_BACK,
            StageStatus.STALE,
            StageStatus.SKIPPED,
            StageStatus.SAFE_STOPPED,
            StageStatus.CANCELLED,
        }:
            stage.completed_at = now
        if target is StageStatus.STALE:
            stage.lease_token = None
            stage.claim_owner = None
            stage.lease_expires_at = None
        if target is StageStatus.SUCCEEDED:
            workflow.last_successful_stage = stage.stage_name
        await self.audit_store_factory(session).append(
            workflow.id,
            event_type=event_type,
            actor_type=context.actor_type,
            actor_id=context.actor_id,
            stage_run_id=stage.id,
            trace_id=context.trace_id,
            before_state=previous.value,
            after_state=target.value,
            reason=reason,
            payload={
                "entity_version": stage.version,
                "stage_name": stage.stage_name,
                "generation": stage.generation,
                "attempt": stage.attempt,
            },
        )

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
