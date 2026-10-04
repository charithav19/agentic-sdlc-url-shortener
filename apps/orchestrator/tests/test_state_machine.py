"""Explicit legal and illegal workflow/stage transitions."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.orchestration.commands import TransitionContext
from app.orchestration.contracts import ScenarioType, StageStatus, WorkflowStatus
from app.orchestration.orchestrator import WorkflowOrchestrator
from app.orchestration.state_machine import (
    STAGE_TRANSITIONS,
    WORKFLOW_TRANSITIONS,
    InvalidTransitionError,
    require_stage_transition,
    require_workflow_transition,
)
from app.persistence.service import WorkflowPersistenceService
from app.persistence.unit_of_work import UnitOfWork


def test_required_legal_stage_transition_rules() -> None:
    required = {
        (StageStatus.PENDING, StageStatus.BLOCKED),
        (StageStatus.BLOCKED, StageStatus.READY),
        (StageStatus.READY, StageStatus.RUNNING),
        (StageStatus.RUNNING, StageStatus.SUCCEEDED),
        (StageStatus.RUNNING, StageStatus.FAILED),
        (StageStatus.FAILED, StageStatus.RETRY_PENDING),
        (StageStatus.SUCCEEDED, StageStatus.STALE),
    }
    for current, target in required:
        require_stage_transition(current, target)
        assert target in STAGE_TRANSITIONS[current]


def test_every_status_has_an_explicit_transition_rule() -> None:
    assert set(STAGE_TRANSITIONS) == set(StageStatus)
    assert set(WORKFLOW_TRANSITIONS) == set(WorkflowStatus)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (StageStatus.PENDING, StageStatus.SUCCEEDED),
        (StageStatus.BLOCKED, StageStatus.RUNNING),
        (StageStatus.READY, StageStatus.SUCCEEDED),
        (StageStatus.SUCCEEDED, StageStatus.RUNNING),
        (StageStatus.CANCELLED, StageStatus.READY),
    ],
)
def test_illegal_stage_transitions_fail(current: StageStatus, target: StageStatus) -> None:
    with pytest.raises(InvalidTransitionError, match="Illegal stage transition"):
        require_stage_transition(current, target)


def test_workflow_completion_requires_verified_release_gates() -> None:
    with pytest.raises(InvalidTransitionError, match="verified release gates"):
        require_workflow_transition(WorkflowStatus.RUNNING, WorkflowStatus.COMPLETED)
    require_workflow_transition(
        WorkflowStatus.RUNNING,
        WorkflowStatus.COMPLETED,
        completion_verified=True,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_orchestrator_persists_legal_stage_transition_chain(
    phase6_factory: async_sessionmaker[AsyncSession],
) -> None:
    persistence = WorkflowPersistenceService(phase6_factory)
    workflow_id = await persistence.create_workflow(
        scenario_type=ScenarioType.GREENFIELD,
        provider_mode="fake",
        workspace_ref="state-machine",
    )
    stage_id = await persistence.add_stage_attempt(
        workflow_id,
        stage_name="IMPLEMENTATION",
        generation=1,
        attempt=1,
        executor="implementation_specialist",
    )
    orchestrator = WorkflowOrchestrator(phase6_factory)
    context = TransitionContext(actor_type="SYSTEM", actor_id="orchestrator")

    for status in (
        StageStatus.BLOCKED,
        StageStatus.READY,
        StageStatus.RUNNING,
        StageStatus.SUCCEEDED,
        StageStatus.STALE,
    ):
        await orchestrator.transition_stage(stage_id, status, context)

    async with UnitOfWork.open(phase6_factory) as unit:
        stage = await unit.stages.get(stage_id)
        workflow = await unit.workflows.get(workflow_id)
        events = await unit.audit.page(workflow_id)
        assert stage.status == StageStatus.STALE
        assert stage.version == 6
        assert stage.started_at is not None
        assert stage.completed_at is not None
        assert workflow.last_successful_stage == "IMPLEMENTATION"
        transitions = [event for event in events if event.event_type == "STAGE_STATUS_CHANGED"]
        assert [event.after_state for event in transitions] == [
            "BLOCKED",
            "READY",
            "RUNNING",
            "SUCCEEDED",
            "STALE",
        ]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_orchestrator_rejects_illegal_transition_without_audit(
    phase6_factory: async_sessionmaker[AsyncSession],
) -> None:
    persistence = WorkflowPersistenceService(phase6_factory)
    workflow_id = await persistence.create_workflow(
        scenario_type=ScenarioType.BROWNFIELD,
        provider_mode="fake",
        workspace_ref="illegal-transition",
    )
    stage_id = await persistence.add_stage_attempt(
        workflow_id,
        stage_name="BUILD_VALIDATION",
        generation=1,
        attempt=1,
        executor="build_runner",
    )
    orchestrator = WorkflowOrchestrator(phase6_factory)

    with pytest.raises(InvalidTransitionError, match="PENDING -> SUCCEEDED"):
        await orchestrator.transition_stage(
            stage_id,
            StageStatus.SUCCEEDED,
            TransitionContext(actor_type="SYSTEM", actor_id="orchestrator"),
        )

    async with UnitOfWork.open(phase6_factory) as unit:
        stage = await unit.stages.get(stage_id)
        events = await unit.audit.page(workflow_id)
        assert stage.status == StageStatus.PENDING
        assert stage.version == 1
        assert all(event.event_type != "STAGE_STATUS_CHANGED" for event in events)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_workflow_transitions_are_audited(
    phase6_factory: async_sessionmaker[AsyncSession],
) -> None:
    persistence = WorkflowPersistenceService(phase6_factory)
    workflow_id = await persistence.create_workflow(
        scenario_type=ScenarioType.AMBIGUOUS,
        provider_mode="fake",
        workspace_ref="workflow-state",
    )
    orchestrator = WorkflowOrchestrator(phase6_factory)
    result = await orchestrator.transition_workflow(
        workflow_id,
        WorkflowStatus.RUNNING,
        TransitionContext(
            actor_type="HUMAN",
            actor_id="operator-1",
            reason="Start approved workflow",
            expected_version=1,
        ),
    )

    assert result.previous_status == "CREATED"
    assert result.current_status == "RUNNING"
    assert result.version == 2
    async with UnitOfWork.open(phase6_factory) as unit:
        workflow = await unit.workflows.get(workflow_id)
        events = await unit.audit.page(workflow_id)
        event = events[-1]
        assert workflow.status == WorkflowStatus.RUNNING
        assert event.id == result.audit_event_id
        assert event.event_type == "WORKFLOW_STATUS_CHANGED"
        assert event.before_state == "CREATED"
        assert event.after_state == "RUNNING"
        assert event.actor_type == "HUMAN"
        assert event.actor_id == "operator-1"
        assert event.reason == "Start approved workflow"
