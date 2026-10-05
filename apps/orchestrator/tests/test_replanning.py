"""Selective requirement replanning preserves unrelated work."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.dependencies import get_orchestrator
from app.artifacts.candidate_refs import ArtifactStatus
from app.artifacts.schemas import ArtifactInput
from app.governance.approvals import ApprovalDecision, ApprovalStatus, ApprovalType
from app.governance.auth import ReviewerIdentity, require_reviewer
from app.main import app
from app.orchestration.commands import TransitionContext
from app.orchestration.contracts import ScenarioType, StageStatus, WorkflowStatus
from app.orchestration.orchestrator import WorkflowOrchestrator
from app.persistence.models import (
    Approval,
    Artifact,
    ArtifactLifecycle,
    ArtifactLineage,
    StageRun,
    WorkflowRun,
)
from app.persistence.service import WorkflowPersistenceService
from app.persistence.unit_of_work import UnitOfWork


async def succeeded_stage(
    persistence: WorkflowPersistenceService,
    orchestrator: WorkflowOrchestrator,
    workflow_id: uuid.UUID,
    name: str,
) -> uuid.UUID:
    stage_id = await persistence.add_stage_attempt(
        workflow_id,
        stage_name=name,
        generation=1,
        attempt=1,
        executor=name.lower(),
    )
    context = TransitionContext(actor_type="SYSTEM", actor_id="replan-fixture")
    for stage_status in (StageStatus.READY, StageStatus.RUNNING, StageStatus.SUCCEEDED):
        await orchestrator.transition_stage(stage_id, stage_status, context)
    return stage_id


async def artifact(
    persistence: WorkflowPersistenceService,
    workflow_id: uuid.UUID,
    *,
    name: str,
    artifact_type: str,
    producer_stage_run_id: uuid.UUID | None = None,
    requirement_ids: list[str] | None = None,
    component_ids: list[str] | None = None,
    content: dict | None = None,
):
    return await persistence.store_artifact(
        workflow_id,
        ArtifactInput(
            logical_name=name,
            artifact_type=artifact_type,
            schema_version="1",
            content=content or {"name": name, "revision": 1},
            producer_stage_run_id=producer_stage_run_id,
            requirement_ids=requirement_ids or ["REQ-EXPIRY"],
            component_ids=component_ids or ["URL-REDIRECT"],
        ),
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_requirement_update_selectively_stales_descendants_and_returns_to_planning(
    phase6_factory: async_sessionmaker[AsyncSession],
) -> None:
    persistence = WorkflowPersistenceService(phase6_factory)
    orchestrator = WorkflowOrchestrator(phase6_factory)
    workflow_id = await persistence.create_workflow(
        scenario_type=ScenarioType.BROWNFIELD,
        provider_mode="fake",
        workspace_ref="expiry-selective-replan",
    )
    await orchestrator.transition_workflow(
        workflow_id,
        WorkflowStatus.RUNNING,
        TransitionContext(actor_type="SYSTEM", actor_id="replan-fixture", expected_version=1),
    )

    task_stage = await succeeded_stage(persistence, orchestrator, workflow_id, "TASK_DECOMPOSITION")
    architecture_stage = await succeeded_stage(
        persistence, orchestrator, workflow_id, "ARCHITECTURE_DESIGN"
    )
    implementation_stage = await succeeded_stage(
        persistence, orchestrator, workflow_id, "IMPLEMENTATION"
    )
    test_stage = await succeeded_stage(persistence, orchestrator, workflow_id, "TEST_DESIGN")
    documentation_stage = await succeeded_stage(
        persistence, orchestrator, workflow_id, "DOCUMENTATION_DRAFT"
    )
    analytics_stage = await succeeded_stage(persistence, orchestrator, workflow_id, "ANALYTICS")

    requirement_v1 = await artifact(
        persistence,
        workflow_id,
        name="requirement",
        artifact_type="requirement",
        content={"requirement": "Expired links return 404."},
    )
    plan_v1 = await artifact(
        persistence,
        workflow_id,
        name="task-plan",
        artifact_type="plan",
        producer_stage_run_id=task_stage,
    )
    architecture_v1 = await artifact(
        persistence,
        workflow_id,
        name="architecture",
        artifact_type="architecture",
        producer_stage_run_id=architecture_stage,
    )
    implementation_v1 = await artifact(
        persistence,
        workflow_id,
        name="implementation",
        artifact_type="implementation",
        producer_stage_run_id=implementation_stage,
    )
    tests_v1 = await artifact(
        persistence,
        workflow_id,
        name="expiry-tests",
        artifact_type="test_plan",
        producer_stage_run_id=test_stage,
    )
    documentation_v1 = await artifact(
        persistence,
        workflow_id,
        name="api-documentation",
        artifact_type="documentation",
        producer_stage_run_id=documentation_stage,
    )
    analytics_v1 = await artifact(
        persistence,
        workflow_id,
        name="analytics-design",
        artifact_type="architecture",
        producer_stage_run_id=analytics_stage,
        requirement_ids=["REQ-ANALYTICS"],
        component_ids=["ANALYTICS"],
    )

    for parent, child, relationship in (
        (requirement_v1, plan_v1, "DERIVED_FROM"),
        (plan_v1, architecture_v1, "DERIVED_FROM"),
        (architecture_v1, implementation_v1, "IMPLEMENTS"),
        (architecture_v1, tests_v1, "VALIDATES"),
        (architecture_v1, documentation_v1, "DOCUMENTS"),
    ):
        await persistence.link_artifacts(
            workflow_id,
            parent_artifact_id=parent.id,
            child_artifact_id=child.id,
            relationship=relationship,
            requirement_ids=["REQ-EXPIRY"],
            component_ids=["URL-REDIRECT"],
        )

    checkpoint = await orchestrator.request_approval_checkpoint(
        workflow_id,
        approval_type=ApprovalType.ARCHITECTURE,
        artifact_id=architecture_v1.id,
        artifact_version=architecture_v1.version,
        context=TransitionContext(
            actor_type="SYSTEM",
            actor_id="replan-fixture",
            expected_version=2,
        ),
    )
    await orchestrator.decide_approval(
        workflow_id,
        approval_id=checkpoint.approval_id,
        artifact_id=architecture_v1.id,
        artifact_version=architecture_v1.version,
        decision=ApprovalDecision.APPROVED,
        reviewer_id="architecture-reviewer",
        reason="Architecture V1 approved",
        context=TransitionContext(
            actor_type="HUMAN",
            actor_id="architecture-reviewer",
            expected_version=3,
        ),
    )
    async with UnitOfWork.open(phase6_factory) as unit:
        unit.session.add(
            ArtifactLifecycle(
                artifact_id=analytics_v1.id,
                workflow_id=workflow_id,
                status=ArtifactStatus.APPROVED.value,
                active=True,
                version=1,
            )
        )

    update_id = uuid.uuid4()
    app.dependency_overrides[get_orchestrator] = lambda: orchestrator
    app.dependency_overrides[require_reviewer] = lambda: ReviewerIdentity(
        reviewer_id="requirements-owner"
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://orchestrator.test"
        ) as client:
            request_body = {
                "requirement": "Expired links return 410 Gone.",
                "updateId": str(update_id),
                "expectedWorkflowVersion": 4,
                "reason": "Align expiry behavior with the revised contract",
            }
            response = await client.post(
                f"/api/v1/workflows/{workflow_id}/requirements", json=request_body
            )
            repeated = await client.post(
                f"/api/v1/workflows/{workflow_id}/requirements", json=request_body
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201, response.text
    assert repeated.status_code == 201, repeated.text
    body = response.json()
    assert repeated.json() == body
    assert body["updateId"] == str(update_id)
    assert body["requirementVersion"] == 2
    assert body["generation"] == 2
    assert body["workflowStatus"] == "RUNNING"
    assert body["currentStage"] == "TASK_DECOMPOSITION"
    assert body["architectureApprovalRequired"] is True
    assert "ANALYTICS" not in body["affectedStages"]
    assert set(body["staleArtifactIds"]) == {
        str(plan_v1.id),
        str(architecture_v1.id),
        str(implementation_v1.id),
        str(tests_v1.id),
        str(documentation_v1.id),
    }

    async with UnitOfWork.open(phase6_factory) as unit:
        workflow = await unit.session.get(WorkflowRun, workflow_id)
        requirements = list(
            await unit.session.scalars(
                select(Artifact)
                .where(
                    Artifact.workflow_id == workflow_id,
                    Artifact.logical_name == "requirement",
                )
                .order_by(Artifact.version)
            )
        )
        stale_lifecycles = list(
            await unit.session.scalars(
                select(ArtifactLifecycle).where(
                    ArtifactLifecycle.artifact_id.in_(
                        (
                            architecture_v1.id,
                            implementation_v1.id,
                            tests_v1.id,
                            documentation_v1.id,
                        )
                    )
                )
            )
        )
        analytics_lifecycle = await unit.session.get(ArtifactLifecycle, analytics_v1.id)
        approval = await unit.session.get(Approval, checkpoint.approval_id)
        supersedes = await unit.session.scalar(
            select(ArtifactLineage).where(
                ArtifactLineage.parent_artifact_id == requirement_v1.id,
                ArtifactLineage.child_artifact_id == requirements[1].id,
                ArtifactLineage.relationship == "SUPERSEDES",
            )
        )
        new_stages = list(
            await unit.session.scalars(
                select(StageRun)
                .where(StageRun.workflow_id == workflow_id, StageRun.generation == 2)
                .order_by(StageRun.stage_name)
            )
        )
        old_analytics_stage = await unit.session.get(StageRun, analytics_stage)
        old_affected_stages = list(
            await unit.session.scalars(
                select(StageRun).where(
                    StageRun.id.in_(
                        (
                            task_stage,
                            architecture_stage,
                            implementation_stage,
                            test_stage,
                            documentation_stage,
                        )
                    )
                )
            )
        )
        events = await unit.audit.page(workflow_id, limit=500)

        assert workflow is not None
        assert workflow.status is WorkflowStatus.RUNNING
        assert workflow.generation == 2
        assert workflow.requirement_version == 2
        assert workflow.last_successful_stage == "REQUIREMENT_ANALYSIS"
        assert [item.version for item in requirements] == [1, 2]
        assert requirements[0].content == {"requirement": "Expired links return 404."}
        assert requirements[1].content["requirement"] == "Expired links return 410 Gone."
        assert supersedes is not None
        assert {item.artifact_id for item in stale_lifecycles} == {
            architecture_v1.id,
            implementation_v1.id,
            tests_v1.id,
            documentation_v1.id,
        }
        assert all(item.status == ArtifactStatus.STALE.value for item in stale_lifecycles)
        assert approval is not None and approval.status == ApprovalStatus.INVALIDATED.value
        assert analytics_lifecycle is not None
        assert analytics_lifecycle.status == ArtifactStatus.APPROVED.value
        assert analytics_lifecycle.active is True
        assert old_analytics_stage is not None
        assert old_analytics_stage.status is StageStatus.SUCCEEDED
        assert all(stage.status is StageStatus.STALE for stage in old_affected_stages)
        new_statuses = {stage.stage_name: stage.status for stage in new_stages}
        assert new_statuses["REQUIREMENT_ANALYSIS"] is StageStatus.SUCCEEDED
        assert new_statuses["TASK_DECOMPOSITION"] is StageStatus.READY
        assert new_statuses["ARCHITECTURE_DESIGN"] is StageStatus.BLOCKED
        assert new_statuses["ARCHITECTURE_APPROVAL"] is StageStatus.BLOCKED
        replan_events = [
            event.event_type
            for event in events
            if event.event_type in {"REPLAN_STARTED", "REPLAN_COMPLETED"}
        ]
        assert replan_events == ["REPLAN_STARTED", "REPLAN_COMPLETED"]
