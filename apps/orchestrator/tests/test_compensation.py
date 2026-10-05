"""Semantic rollback preserves rejected evidence and restores approved state."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.artifacts.candidate_refs import ArtifactStatus
from app.artifacts.schemas import ArtifactInput, ArtifactRef
from app.governance.approvals import ApprovalDecision, ApprovalType
from app.orchestration.commands import TransitionContext
from app.orchestration.compensation import CompensationCoordinator
from app.orchestration.contracts import ScenarioType, StageStatus, WorkflowStatus
from app.orchestration.failure_classifier import SecurityViolationFailure
from app.orchestration.graph import RetryPolicy, StageDefinition, build_graph
from app.orchestration.orchestrator import WorkflowOrchestrator
from app.orchestration.registry import GraphRegistry
from app.orchestration.scheduler import WorkflowScheduler
from app.persistence.models import (
    Approval,
    Artifact,
    ArtifactLifecycle,
    CandidateReference,
    Compensation,
    StageRun,
    WorkflowRun,
)
from app.persistence.service import WorkflowPersistenceService
from app.persistence.unit_of_work import UnitOfWork


def compensation_graph():
    stages = (
        StageDefinition(
            name="IMPLEMENTATION",
            dependencies=(),
            executor="implementation",
            entry_gate="always",
            exit_gate="implementation_complete",
            retry_policy=RetryPolicy(max_attempts=2),
            fallback=None,
            approval_required=False,
        ),
        StageDefinition(
            name="SECURITY_VALIDATION",
            dependencies=("IMPLEMENTATION",),
            executor="security",
            entry_gate="implementation_complete",
            exit_gate="security_complete",
            retry_policy=RetryPolicy(max_attempts=2),
            fallback=None,
            approval_required=False,
        ),
    )
    registry = GraphRegistry(
        executors=frozenset({"implementation", "security"}),
        gates=frozenset({"always", "implementation_complete", "security_complete"}),
        retryable_errors=frozenset(),
    )
    return build_graph("compensation-test", stages, registry=registry)


async def approve_release(
    orchestrator: WorkflowOrchestrator,
    workflow_id: uuid.UUID,
    artifact: ArtifactRef,
) -> uuid.UUID:
    checkpoint = await orchestrator.request_approval_checkpoint(
        workflow_id,
        approval_type=ApprovalType.RELEASE,
        artifact_id=artifact.id,
        artifact_version=artifact.version,
        context=TransitionContext(
            actor_type="SYSTEM",
            actor_id="compensation-test",
            expected_version=2,
        ),
    )
    await orchestrator.decide_approval(
        workflow_id,
        approval_id=checkpoint.approval_id,
        artifact_id=artifact.id,
        artifact_version=artifact.version,
        decision=ApprovalDecision.APPROVED,
        reviewer_id="reviewer-1",
        reason="Approved baseline implementation",
        context=TransitionContext(
            actor_type="HUMAN",
            actor_id="reviewer-1",
            expected_version=3,
        ),
    )
    return checkpoint.approval_id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_security_failure_rolls_back_candidate_and_preserves_approved_state(
    phase6_factory: async_sessionmaker[AsyncSession],
) -> None:
    persistence = WorkflowPersistenceService(phase6_factory)
    orchestrator = WorkflowOrchestrator(phase6_factory)
    workflow_id = await persistence.create_workflow(
        scenario_type=ScenarioType.GREENFIELD,
        provider_mode="fake",
        workspace_ref="semantic-rollback",
    )
    await orchestrator.transition_workflow(
        workflow_id,
        WorkflowStatus.RUNNING,
        TransitionContext(actor_type="SYSTEM", actor_id="compensation-test"),
    )
    approved = await persistence.store_artifact(
        workflow_id,
        ArtifactInput(
            logical_name="implementation-candidate",
            artifact_type="implementation_candidate",
            schema_version="1",
            content={"revision": "approved", "files": ["app.py"]},
        ),
    )
    approved_decision_id = await approve_release(orchestrator, workflow_id, approved)
    await persistence.activate_approved_candidate(workflow_id, approved.id)

    implementation_id = await persistence.add_stage_attempt(
        workflow_id,
        stage_name="IMPLEMENTATION",
        generation=1,
        attempt=1,
        executor="implementation",
    )
    transition = TransitionContext(actor_type="SYSTEM", actor_id="compensation-test")
    for status in (StageStatus.READY, StageStatus.RUNNING, StageStatus.SUCCEEDED):
        await orchestrator.transition_stage(implementation_id, status, transition)
    candidate = await persistence.store_artifact(
        workflow_id,
        ArtifactInput(
            logical_name="implementation-candidate",
            artifact_type="implementation_candidate",
            schema_version="1",
            content={"revision": "candidate", "files": ["app.py", "unsafe.py"]},
            producer_stage_run_id=implementation_id,
        ),
    )
    await persistence.stage_candidate_for_validation(workflow_id, candidate.id)
    security_id = await persistence.add_stage_attempt(
        workflow_id,
        stage_name="SECURITY_VALIDATION",
        generation=1,
        attempt=1,
        executor="security",
        input_artifacts=[candidate],
    )

    async def security_failure(_claim):
        raise SecurityViolationFailure("mandatory security validation rejected candidate")

    scheduler = WorkflowScheduler(
        phase6_factory,
        compensation_graph(),
        {"security": security_failure},
        scheduler_id="compensation-test",
    )
    cycle = await scheduler.run_cycle(workflow_id)

    assert cycle.recovery[0].compensation_id is not None
    async with UnitOfWork.open(phase6_factory) as unit:
        workflow = await unit.session.get(WorkflowRun, workflow_id)
        security = await unit.session.get(StageRun, security_id)
        rejected = await unit.session.get(Artifact, candidate.id)
        rejected_lifecycle = await unit.session.get(ArtifactLifecycle, candidate.id)
        approved_artifact = await unit.session.get(Artifact, approved.id)
        approved_lifecycle = await unit.session.get(ArtifactLifecycle, approved.id)
        reference = await unit.session.get(
            CandidateReference, (workflow_id, "implementation-candidate")
        )
        compensation = await unit.session.get(Compensation, cycle.recovery[0].compensation_id)
        approved_decision = await unit.session.get(Approval, approved_decision_id)
        events = await unit.audit.page(workflow_id)

        assert workflow is not None and workflow.status is WorkflowStatus.SAFE_STOPPED
        assert security is not None and security.status is StageStatus.SAFE_STOPPED
        assert rejected is not None and rejected.content["revision"] == "candidate"
        assert rejected_lifecycle is not None
        assert rejected_lifecycle.status == ArtifactStatus.ROLLED_BACK.value
        assert rejected_lifecycle.active is False
        assert approved_artifact is not None and approved_artifact.content["revision"] == "approved"
        assert approved_lifecycle is not None
        assert approved_lifecycle.status == ArtifactStatus.APPROVED.value
        assert approved_lifecycle.active is True
        assert reference is not None
        assert reference.active_artifact_id == approved.id
        assert reference.approved_artifact_id == approved.id
        assert compensation is not None and compensation.status == "COMPLETED"
        assert compensation.restored_artifact_id == approved.id
        assert approved_decision is not None and approved_decision.status == "APPROVED"
        rollback_events = [
            event.event_type
            for event in events
            if event.event_type in {"ROLLBACK_STARTED", "ROLLBACK_COMPLETED"}
        ]
        assert rollback_events == ["ROLLBACK_STARTED", "ROLLBACK_COMPLETED"]

    repeated = await CompensationCoordinator(phase6_factory).compensate(
        security_id,
        candidate_artifact_id=candidate.id,
        failure_reason="mandatory security validation rejected candidate",
        context=transition,
    )
    assert repeated.compensation_id == cycle.recovery[0].compensation_id
    assert repeated.idempotent is True
    async with UnitOfWork.open(phase6_factory) as unit:
        events = await unit.audit.page(workflow_id)
        assert sum(event.event_type == "ROLLBACK_STARTED" for event in events) == 1
        assert sum(event.event_type == "ROLLBACK_COMPLETED" for event in events) == 1
