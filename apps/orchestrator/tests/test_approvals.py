"""Exact-version human approval checkpoints and HTTP decisions."""

import uuid

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.dependencies import get_orchestrator
from app.artifacts.schemas import ArtifactInput, ArtifactRef
from app.config import Settings
from app.governance.approvals import (
    ApprovalStatus,
    ApprovalType,
)
from app.governance.auth import ReviewerIdentity, require_reviewer
from app.main import app
from app.orchestration.commands import TransitionContext
from app.orchestration.contracts import ScenarioType, StageStatus, WorkflowStatus
from app.orchestration.orchestrator import WorkflowOrchestrator
from app.orchestration.state_machine import InvalidTransitionError
from app.persistence.models import Approval
from app.persistence.service import WorkflowPersistenceService
from app.persistence.unit_of_work import UnitOfWork


def test_approval_vocabularies_are_explicit() -> None:
    assert {value.value for value in ApprovalType} == {
        "ARCHITECTURE",
        "HIGH_IMPACT_CHANGE",
        "ASSUMPTION",
        "RELEASE",
    }


def test_local_reviewer_credential_is_required_and_identity_is_explicit() -> None:
    settings = Settings(local_reviewer_token="review-secret")
    reviewer = require_reviewer(settings, "Bearer review-secret", "human-reviewer")
    assert reviewer == ReviewerIdentity(reviewer_id="human-reviewer")

    with pytest.raises(HTTPException) as denied:
        require_reviewer(settings, "Bearer agent-credential", "agent")
    assert denied.value.status_code == 401
    assert {value.value for value in ApprovalStatus} == {
        "PENDING",
        "APPROVED",
        "REJECTED",
        "INVALIDATED",
    }


async def running_workflow_with_artifact(
    factory: async_sessionmaker[AsyncSession],
    *,
    logical_name: str,
) -> tuple[uuid.UUID, ArtifactRef, WorkflowOrchestrator, WorkflowPersistenceService]:
    persistence = WorkflowPersistenceService(factory)
    orchestrator = WorkflowOrchestrator(factory)
    workflow_id = await persistence.create_workflow(
        scenario_type=ScenarioType.GREENFIELD,
        provider_mode="fake",
        workspace_ref=f"approval-{logical_name}",
    )
    await orchestrator.transition_workflow(
        workflow_id,
        WorkflowStatus.RUNNING,
        TransitionContext(
            actor_type="SYSTEM",
            actor_id="orchestrator",
            expected_version=1,
        ),
    )
    artifact = await persistence.store_artifact(
        workflow_id,
        ArtifactInput(
            logical_name=logical_name,
            artifact_type=logical_name,
            schema_version="1",
            content={"logicalName": logical_name, "revision": 1},
        ),
    )
    return workflow_id, artifact, orchestrator, persistence


async def submit_decision(
    orchestrator: WorkflowOrchestrator,
    workflow_id: uuid.UUID,
    approval_id: uuid.UUID,
    artifact: ArtifactRef,
    *,
    status: str,
    workflow_version: int,
    reason: str | None = None,
) -> tuple[int, dict]:
    app.dependency_overrides[get_orchestrator] = lambda: orchestrator
    app.dependency_overrides[require_reviewer] = lambda: ReviewerIdentity(reviewer_id="reviewer-1")
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://orchestrator.test"
        ) as client:
            response = await client.post(
                f"/api/v1/workflows/{workflow_id}/approvals",
                json={
                    "approvalId": str(approval_id),
                    "artifactId": str(artifact.id),
                    "artifactVersion": artifact.version,
                    "status": status,
                    "reason": reason,
                    "workflowVersion": workflow_version,
                },
            )
        return response.status_code, response.json()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_architecture_checkpoint_pauses_workflow_before_implementation(
    phase6_factory: async_sessionmaker[AsyncSession],
) -> None:
    workflow_id, artifact, orchestrator, persistence = await running_workflow_with_artifact(
        phase6_factory, logical_name="architecture"
    )
    implementation_stage_id = await persistence.add_stage_attempt(
        workflow_id,
        stage_name="IMPLEMENTATION",
        generation=1,
        attempt=1,
        executor="implementation_specialist",
    )
    await orchestrator.transition_stage(
        implementation_stage_id,
        StageStatus.BLOCKED,
        TransitionContext(actor_type="SYSTEM", actor_id="orchestrator"),
    )
    await orchestrator.transition_stage(
        implementation_stage_id,
        StageStatus.READY,
        TransitionContext(actor_type="SYSTEM", actor_id="orchestrator"),
    )

    checkpoint = await orchestrator.request_approval_checkpoint(
        workflow_id,
        approval_type=ApprovalType.ARCHITECTURE,
        artifact_id=artifact.id,
        artifact_version=artifact.version,
        context=TransitionContext(
            actor_type="SYSTEM",
            actor_id="orchestrator",
            expected_version=2,
            reason="Architecture must be approved before implementation",
        ),
    )

    assert checkpoint.status is ApprovalStatus.PENDING
    assert checkpoint.workflow_status is WorkflowStatus.WAITING_FOR_APPROVAL
    assert checkpoint.artifact_id == artifact.id
    assert checkpoint.artifact_version == artifact.version
    with pytest.raises(InvalidTransitionError, match="WAITING_FOR_APPROVAL"):
        await orchestrator.transition_stage(
            implementation_stage_id,
            StageStatus.RUNNING,
            TransitionContext(actor_type="SYSTEM", actor_id="orchestrator"),
        )
    async with UnitOfWork.open(phase6_factory) as unit:
        workflow = await unit.workflows.get(workflow_id)
        events = await unit.audit.page(workflow_id)
        assert workflow.status is WorkflowStatus.WAITING_FOR_APPROVAL
        assert [event.event_type for event in events[-2:]] == [
            "APPROVAL_REQUESTED",
            "WORKFLOW_STATUS_CHANGED",
        ]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_approved_architecture_resumes_workflow_through_api(
    phase6_factory: async_sessionmaker[AsyncSession],
) -> None:
    workflow_id, artifact, orchestrator, _ = await running_workflow_with_artifact(
        phase6_factory, logical_name="architecture-resume"
    )
    checkpoint = await orchestrator.request_approval_checkpoint(
        workflow_id,
        approval_type=ApprovalType.ARCHITECTURE,
        artifact_id=artifact.id,
        artifact_version=artifact.version,
        context=TransitionContext(actor_type="SYSTEM", actor_id="orchestrator", expected_version=2),
    )

    status_code, body = await submit_decision(
        orchestrator,
        workflow_id,
        checkpoint.approval_id,
        artifact,
        status="APPROVED",
        workflow_version=3,
        reason="Architecture is acceptable",
    )

    assert status_code == 200
    assert body["status"] == "APPROVED"
    assert body["approvalType"] == "ARCHITECTURE"
    assert body["workflowStatus"] == "RUNNING"
    assert body["artifactVersion"] == artifact.version
    async with UnitOfWork.open(phase6_factory) as unit:
        approval = await unit.session.get(Approval, checkpoint.approval_id)
        workflow = await unit.workflows.get(workflow_id)
        assert approval is not None and approval.reviewer_id == "reviewer-1"
        assert workflow.status is WorkflowStatus.RUNNING


@pytest.mark.integration
@pytest.mark.asyncio
async def test_rejection_keeps_dependent_work_blocked(
    phase6_factory: async_sessionmaker[AsyncSession],
) -> None:
    workflow_id, artifact, orchestrator, _ = await running_workflow_with_artifact(
        phase6_factory, logical_name="architecture-rejected"
    )
    checkpoint = await orchestrator.request_approval_checkpoint(
        workflow_id,
        approval_type=ApprovalType.ARCHITECTURE,
        artifact_id=artifact.id,
        artifact_version=artifact.version,
        context=TransitionContext(actor_type="SYSTEM", actor_id="orchestrator", expected_version=2),
    )

    status_code, body = await submit_decision(
        orchestrator,
        workflow_id,
        checkpoint.approval_id,
        artifact,
        status="REJECTED",
        workflow_version=3,
        reason="Threat model is incomplete",
    )

    assert status_code == 200
    assert body["status"] == "REJECTED"
    assert body["workflowStatus"] == "WAITING_FOR_APPROVAL"
    retry_status, _ = await submit_decision(
        orchestrator,
        workflow_id,
        checkpoint.approval_id,
        artifact,
        status="APPROVED",
        workflow_version=3,
        reason="Attempt to override rejection",
    )
    assert retry_status == 409


@pytest.mark.integration
@pytest.mark.asyncio
async def test_wrong_artifact_version_is_rejected_without_deciding(
    phase6_factory: async_sessionmaker[AsyncSession],
) -> None:
    workflow_id, artifact, orchestrator, _ = await running_workflow_with_artifact(
        phase6_factory, logical_name="architecture-version"
    )
    checkpoint = await orchestrator.request_approval_checkpoint(
        workflow_id,
        approval_type=ApprovalType.ARCHITECTURE,
        artifact_id=artifact.id,
        artifact_version=artifact.version,
        context=TransitionContext(actor_type="SYSTEM", actor_id="orchestrator", expected_version=2),
    )
    wrong = artifact.model_copy(update={"version": artifact.version + 1})

    status_code, body = await submit_decision(
        orchestrator,
        workflow_id,
        checkpoint.approval_id,
        wrong,
        status="APPROVED",
        workflow_version=3,
    )

    assert status_code == 409
    assert "exactly match" in body["error"]["message"]
    async with UnitOfWork.open(phase6_factory) as unit:
        approval = await unit.session.get(Approval, checkpoint.approval_id)
        workflow = await unit.workflows.get(workflow_id)
        assert approval is not None and approval.status == ApprovalStatus.PENDING.value
        assert workflow.status is WorkflowStatus.WAITING_FOR_APPROVAL


@pytest.mark.integration
@pytest.mark.asyncio
async def test_new_artifact_version_invalidates_prior_approval(
    phase6_factory: async_sessionmaker[AsyncSession],
) -> None:
    workflow_id, artifact, orchestrator, persistence = await running_workflow_with_artifact(
        phase6_factory, logical_name="architecture-stale"
    )
    checkpoint = await orchestrator.request_approval_checkpoint(
        workflow_id,
        approval_type=ApprovalType.ARCHITECTURE,
        artifact_id=artifact.id,
        artifact_version=artifact.version,
        context=TransitionContext(actor_type="SYSTEM", actor_id="orchestrator", expected_version=2),
    )
    replacement = await persistence.store_artifact(
        workflow_id,
        ArtifactInput(
            logical_name="architecture-stale",
            artifact_type="architecture",
            schema_version="1",
            content={"logicalName": "architecture-stale", "revision": 2},
        ),
    )

    assert replacement.version == 2
    async with UnitOfWork.open(phase6_factory) as unit:
        approval = await unit.session.get(Approval, checkpoint.approval_id)
        events = await unit.audit.page(workflow_id)
        assert approval is not None and approval.status == ApprovalStatus.INVALIDATED.value
        assert any(event.event_type == "APPROVAL_INVALIDATED" for event in events)

    replacement_checkpoint = await orchestrator.request_approval_checkpoint(
        workflow_id,
        approval_type=ApprovalType.ARCHITECTURE,
        artifact_id=replacement.id,
        artifact_version=replacement.version,
        context=TransitionContext(actor_type="SYSTEM", actor_id="orchestrator", expected_version=3),
    )
    assert replacement_checkpoint.status is ApprovalStatus.PENDING
    assert replacement_checkpoint.workflow_status is WorkflowStatus.WAITING_FOR_APPROVAL


@pytest.mark.integration
@pytest.mark.asyncio
async def test_release_checkpoint_pauses_and_exact_approval_allows_completion(
    phase6_factory: async_sessionmaker[AsyncSession],
) -> None:
    workflow_id, artifact, orchestrator, _ = await running_workflow_with_artifact(
        phase6_factory, logical_name="release-candidate"
    )
    with pytest.raises(InvalidTransitionError, match="verified release gates"):
        await orchestrator.transition_workflow(
            workflow_id,
            WorkflowStatus.COMPLETED,
            TransitionContext(actor_type="SYSTEM", actor_id="orchestrator", expected_version=2),
            completion_verified=True,
        )

    checkpoint = await orchestrator.request_approval_checkpoint(
        workflow_id,
        approval_type=ApprovalType.RELEASE,
        artifact_id=artifact.id,
        artifact_version=artifact.version,
        context=TransitionContext(actor_type="SYSTEM", actor_id="orchestrator", expected_version=2),
    )
    assert checkpoint.workflow_status is WorkflowStatus.WAITING_FOR_APPROVAL

    status_code, body = await submit_decision(
        orchestrator,
        workflow_id,
        checkpoint.approval_id,
        artifact,
        status="APPROVED",
        workflow_version=3,
        reason="Release evidence reviewed",
    )
    assert status_code == 200
    assert body["workflowStatus"] == "RUNNING"

    completed = await orchestrator.transition_workflow(
        workflow_id,
        WorkflowStatus.COMPLETED,
        TransitionContext(actor_type="SYSTEM", actor_id="orchestrator", expected_version=4),
        completion_verified=True,
    )
    assert completed.current_status == WorkflowStatus.COMPLETED.value
