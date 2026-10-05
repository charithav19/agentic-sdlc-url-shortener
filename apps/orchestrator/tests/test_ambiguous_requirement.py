"""Blocking ambiguity pauses all downstream engineering until a human answers."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.contracts import AgentContext, Snapshot
from app.agents.fake_provider import FakeAgentProvider
from app.agents.requirement import RequirementAgent
from app.api.dependencies import get_orchestrator
from app.artifacts.schemas import ArtifactInput
from app.governance.auth import ReviewerIdentity, require_reviewer
from app.main import app
from app.orchestration.clarifications import RequirementAnalysisRunner
from app.orchestration.commands import TransitionContext
from app.orchestration.contracts import ScenarioType, StageStatus, WorkflowStatus
from app.orchestration.graph_loader import load_graph
from app.orchestration.orchestrator import WorkflowOrchestrator
from app.orchestration.scheduler import WorkflowScheduler
from app.orchestration.state_machine import InvalidTransitionError
from app.persistence.models import Artifact, ArtifactLineage, StageRun, WorkflowRun
from app.persistence.service import WorkflowPersistenceService
from app.persistence.unit_of_work import UnitOfWork

QUESTIONS = (
    "Should malicious destination URLs be rejected?",
    "Should HTTPS be enforced?",
    "Should links expire automatically?",
    "Is authentication required to create links?",
    "Should private network URLs be blocked?",
    "Is anti-enumeration required for short codes?",
)

AMBIGUOUS_OUTPUT = {
    "normalized_requirement": "Improve URL-shortener safety controls.",
    "acceptance_criteria": ["Safety behavior is explicitly defined before implementation."],
    "ambiguities": [
        "Destination policy",
        "Transport policy",
        "Expiry policy",
        "Authentication policy",
        "Private-network policy",
        "Identifier enumeration policy",
    ],
    "clarifying_questions": list(QUESTIONS),
    "assumptions": [],
    "blocking_ambiguity": True,
    "risks": ["Implementing an unspecified safety policy can block valid users."],
}

RESOLVED_OUTPUT = {
    "normalized_requirement": (
        "Add explicit malicious-destination, network-address, transport, expiration, "
        "authentication, and short-code enumeration safety policies."
    ),
    "acceptance_criteria": [
        "Reject malicious and private-network destinations.",
        "Keep optional expiration and unpredictable seven-character Base62 codes.",
    ],
    "ambiguities": [],
    "clarifying_questions": [],
    "assumptions": ["HTTP remains allowed and creation remains unauthenticated."],
    "blocking_ambiguity": False,
    "risks": ["Destination reputation data can become stale."],
}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ambiguous_requirement_blocks_downstream_until_clarified(
    phase6_factory: async_sessionmaker[AsyncSession],
) -> None:
    persistence = WorkflowPersistenceService(phase6_factory)
    orchestrator = WorkflowOrchestrator(phase6_factory)
    workflow_id = await persistence.create_workflow(
        scenario_type=ScenarioType.AMBIGUOUS,
        provider_mode="fake",
        workspace_ref="ambiguous-link-safety",
    )
    await orchestrator.transition_workflow(
        workflow_id,
        WorkflowStatus.RUNNING,
        TransitionContext(actor_type="SYSTEM", actor_id="scenario", expected_version=1),
    )
    requirement_v1 = await persistence.store_artifact(
        workflow_id,
        ArtifactInput(
            logical_name="requirement",
            artifact_type="requirement",
            schema_version="1",
            content={"requirement": "Make links safer."},
            requirement_ids=["REQ-SAFETY"],
            component_ids=["URL-CREATION", "URL-REDIRECT"],
        ),
    )
    analysis_stage_id = await persistence.add_stage_attempt(
        workflow_id,
        stage_name="REQUIREMENT_ANALYSIS",
        generation=1,
        attempt=1,
        executor="requirements_specialist",
        input_artifacts=[requirement_v1],
    )
    downstream_ids: dict[str, uuid.UUID] = {}
    for name, executor in (
        ("TASK_DECOMPOSITION", "task_decomposition_specialist"),
        ("ARCHITECTURE_DESIGN", "architecture_specialist"),
        ("IMPLEMENTATION", "implementation_specialist"),
    ):
        downstream_ids[name] = await persistence.add_stage_attempt(
            workflow_id,
            stage_name=name,
            generation=1,
            attempt=1,
            executor=executor,
        )
        await orchestrator.transition_stage(
            downstream_ids[name],
            StageStatus.BLOCKED,
            TransitionContext(actor_type="SYSTEM", actor_id="scenario"),
        )
    await orchestrator.transition_stage(
        analysis_stage_id,
        StageStatus.READY,
        TransitionContext(actor_type="SYSTEM", actor_id="scenario"),
    )

    trace_id = uuid.uuid4()
    analysis = await RequirementAnalysisRunner(
        orchestrator,
        FakeAgentProvider({"RequirementAgent": AMBIGUOUS_OUTPUT}),
    ).run(
        requirement_artifact_id=requirement_v1.id,
        agent_context=AgentContext(
            workflow_id=workflow_id,
            stage_run_id=analysis_stage_id,
            trace_id=trace_id,
            generation=1,
            attempt=1,
            requirement="Make links safer.",
            artifacts=(Snapshot(name="requirement", version=1, content="Make links safer."),),
        ),
        transition_context=TransitionContext(
            actor_type="SYSTEM",
            actor_id="requirement-runner",
            trace_id=trace_id,
        ),
    )

    assert analysis.blocking_ambiguity is True
    assert analysis.workflow_status is WorkflowStatus.WAITING_FOR_CLARIFICATION
    assert analysis.questions == QUESTIONS
    assert analysis.clarification_artifact_id is not None
    assert analysis.clarification_artifact_version == 1

    calls: list[str] = []

    async def record_call(claim):
        calls.append(claim.stage_name)
        return {"stage": claim.stage_name}

    executors = {
        definition.executor: record_call
        for definition in load_graph(blocking_ambiguity=True).stages
    }
    paused_cycle = await WorkflowScheduler(
        phase6_factory,
        load_graph(blocking_ambiguity=True),
        executors,
        scheduler_id="ambiguity-test",
    ).run_cycle(workflow_id)
    assert paused_cycle.work == ()
    assert calls == []
    with pytest.raises(InvalidTransitionError, match="WAITING_FOR_CLARIFICATION"):
        await orchestrator.transition_stage(
            downstream_ids["IMPLEMENTATION"],
            StageStatus.RUNNING,
            TransitionContext(actor_type="SYSTEM", actor_id="scenario"),
        )

    answers = (
        (QUESTIONS[0], "Reject known-malicious destinations using deterministic policy rules."),
        (QUESTIONS[1], "Allow HTTP and HTTPS; do not enforce HTTPS-only."),
        (QUESTIONS[2], "Support optional expiration; do not force a default expiry."),
        (QUESTIONS[3], "Authentication is not required for this local prototype."),
        (QUESTIONS[4], "Reject loopback, link-local, and private-network destinations."),
        (QUESTIONS[5], "Use unpredictable seven-character Base62 codes."),
    )
    app.dependency_overrides[get_orchestrator] = lambda: orchestrator
    app.dependency_overrides[require_reviewer] = lambda: ReviewerIdentity(
        reviewer_id="product-owner"
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://orchestrator.test"
        ) as client:
            response = await client.post(
                f"/api/v1/workflows/{workflow_id}/clarifications",
                json={
                    "clarificationArtifactId": str(analysis.clarification_artifact_id),
                    "clarificationArtifactVersion": analysis.clarification_artifact_version,
                    "answers": [
                        {"question": question, "answer": answer} for question, answer in answers
                    ],
                    "expectedWorkflowVersion": analysis.workflow_version,
                    "reason": "Product owner defined the safety policy",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["workflowStatus"] == "RUNNING"
    assert body["generation"] == 2
    assert body["clarificationArtifactVersion"] == 2
    assert body["requirementVersion"] == 2

    async def rerun_requirement_agent(claim):
        calls.append(claim.stage_name)
        agent_result = await FakeAgentProvider({"RequirementAgent": RESOLVED_OUTPUT}).run(
            RequirementAgent(),
            AgentContext(
                workflow_id=workflow_id,
                stage_run_id=claim.stage_run_id,
                trace_id=uuid.uuid4(),
                generation=claim.generation,
                attempt=claim.attempt,
                requirement="Make links safer, using the submitted clarification answers.",
            ),
        )
        assert agent_result.output.blocking_ambiguity is False
        return agent_result.output.model_dump(mode="json")

    rerun_executors = {**executors, "requirements_specialist": rerun_requirement_agent}
    rerun_cycle = await WorkflowScheduler(
        phase6_factory,
        load_graph(),
        rerun_executors,
        scheduler_id="ambiguity-test-rerun",
    ).run_cycle(workflow_id)
    assert [item.stage_name for item in rerun_cycle.work] == ["REQUIREMENT_ANALYSIS"]
    assert calls == ["REQUIREMENT_ANALYSIS"]
    assert "IMPLEMENTATION" not in calls

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
        clarifications = list(
            await unit.session.scalars(
                select(Artifact)
                .where(
                    Artifact.workflow_id == workflow_id,
                    Artifact.logical_name == "clarification",
                )
                .order_by(Artifact.version)
            )
        )
        supersedes = list(
            await unit.session.scalars(
                select(ArtifactLineage).where(
                    ArtifactLineage.workflow_id == workflow_id,
                    ArtifactLineage.relationship == "SUPERSEDES",
                )
            )
        )
        old_downstream = list(
            await unit.session.scalars(
                select(StageRun).where(StageRun.id.in_(tuple(downstream_ids.values())))
            )
        )
        events = await unit.audit.page(workflow_id, limit=500)

        assert workflow is not None and workflow.generation == 2
        assert [item.version for item in requirements] == [1, 2]
        assert requirements[0].content == {"requirement": "Make links safer."}
        assert len(requirements[1].content["clarifications"]) == len(QUESTIONS)
        assert [item.version for item in clarifications] == [1, 2]
        assert clarifications[0].content["status"] == "PENDING"
        assert clarifications[1].content["status"] == "ANSWERED"
        assert len(supersedes) == 2
        assert all(stage.status is StageStatus.STALE for stage in old_downstream)
        event_types = [event.event_type for event in events]
        assert event_types.index("CLARIFICATION_REQUESTED") < event_types.index("REPLAN_STARTED")
        assert event_types.index("REPLAN_STARTED") < event_types.index("CLARIFICATION_SUBMITTED")
        assert event_types.index("CLARIFICATION_SUBMITTED") < event_types.index("REPLAN_COMPLETED")
