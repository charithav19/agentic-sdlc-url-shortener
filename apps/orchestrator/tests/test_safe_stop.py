import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.errors import AgentTimeout, AgentToolDenied, AgentTransientError
from app.api.recovery import ResumeRequest
from app.orchestration.commands import TransitionContext
from app.orchestration.contracts import StageStatus, WorkflowStatus
from app.orchestration.failure_classifier import (
    CorruptedLineageFailure,
    FailureClassifier,
    FailureCode,
    InvalidRequirementFailure,
    InvalidWorkflowStateFailure,
    PolicyViolationFailure,
    SecurityViolationFailure,
    TemporaryWorkspaceToolFailure,
)
from app.orchestration.recovery import RecoveryAction
from app.orchestration.scheduler import WorkflowScheduler
from app.orchestration.state_machine import InvalidTransitionError
from app.persistence.models import StageRun, WorkflowRun
from app.persistence.unit_of_work import UnitOfWork
from tests.recovery_fixtures import recovery_graph, running_workflow


@pytest.mark.parametrize(
    "error",
    [
        AgentTimeout("timeout"),
        AgentTransientError("provider"),
        TemporaryWorkspaceToolFailure("workspace"),
    ],
)
def test_only_declared_temporary_failures_are_retryable(error) -> None:
    result = FailureClassifier().classify(error)
    assert result.retryable is True
    assert result.safe_stop is False


def test_resume_request_requires_explicit_resolved_cause() -> None:
    with pytest.raises(ValidationError):
        ResumeRequest(
            stageRunId=uuid.uuid4(),
            workflowVersion=3,
            causeResolved=False,
            resolution="not actually resolved",
        )


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (PolicyViolationFailure("policy"), FailureCode.POLICY_VIOLATION),
        (AssertionError("assertion"), FailureCode.FAILED_TEST_ASSERTION),
        (InvalidRequirementFailure("requirement"), FailureCode.INVALID_REQUIREMENT),
        (SecurityViolationFailure("security"), FailureCode.SECURITY_VIOLATION),
        (AgentToolDenied("tool"), FailureCode.FORBIDDEN_TOOL_REQUEST),
        (InvalidWorkflowStateFailure("state"), FailureCode.INVALID_WORKFLOW_STATE),
        (CorruptedLineageFailure("lineage"), FailureCode.CORRUPTED_LINEAGE),
    ],
)
def test_non_retryable_failures_are_classified_for_safe_stop(error, code) -> None:
    result = FailureClassifier().classify(error)
    assert result.code is code
    assert result.retryable is False
    assert result.safe_stop is True
    assert result.recommended_human_action


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "injected",
    [
        PolicyViolationFailure("injected policy violation"),
        AssertionError("injected failed test assertion"),
        InvalidRequirementFailure("injected invalid requirement"),
        SecurityViolationFailure("injected security violation"),
        AgentToolDenied("injected forbidden tool action"),
        InvalidWorkflowStateFailure("injected invalid state"),
        CorruptedLineageFailure("injected corrupt lineage"),
    ],
)
async def test_safe_stop_conditions_block_descendants_and_store_action(
    phase6_factory: async_sessionmaker[AsyncSession],
    injected: Exception,
) -> None:
    workflow_id, a_id, b_id, _ = await running_workflow(phase6_factory)
    descendant_calls = 0

    async def fail(_claim):
        raise injected

    async def descendant(_claim):
        nonlocal descendant_calls
        descendant_calls += 1
        return {"unexpected": True}

    scheduler = WorkflowScheduler(
        phase6_factory,
        recovery_graph(),
        {"primary": fail, "descendant": descendant},
        scheduler_id="safe-stop-test",
    )
    result = await scheduler.run_cycle(workflow_id)
    after_stop = await scheduler.run_cycle(workflow_id)

    assert result.recovery[0].action is RecoveryAction.SAFE_STOPPED
    assert after_stop.work == ()
    assert descendant_calls == 0
    async with UnitOfWork.open(phase6_factory) as unit:
        workflow = await unit.session.get(WorkflowRun, workflow_id)
        failed = await unit.session.get(StageRun, a_id)
        child = await unit.session.get(StageRun, b_id)
        events = await unit.audit.page(workflow_id)
        assert workflow is not None and workflow.status is WorkflowStatus.SAFE_STOPPED
        assert failed is not None and failed.status is StageStatus.SAFE_STOPPED
        assert child is not None and child.status is StageStatus.BLOCKED
        assert workflow.stop_reason and "injected" in workflow.stop_reason
        assert workflow.recommended_human_action
        assert failed.failure_code
        assert any(event.event_type == "STAGE_SAFE_STOPPED" for event in events)
        assert events[-1].after_state == WorkflowStatus.SAFE_STOPPED.value


@pytest.mark.integration
@pytest.mark.asyncio
async def test_safe_stop_retains_last_successful_stage(
    phase6_factory: async_sessionmaker[AsyncSession],
) -> None:
    workflow_id, _, _, _ = await running_workflow(phase6_factory)

    async def succeed(_claim):
        return {"ok": True}

    async def fail(_claim):
        raise SecurityViolationFailure("injected after A succeeded")

    scheduler = WorkflowScheduler(
        phase6_factory,
        recovery_graph(),
        {"primary": succeed, "descendant": fail},
        scheduler_id="last-success-test",
    )
    await scheduler.run_cycle(workflow_id)
    await scheduler.run_cycle(workflow_id)

    async with UnitOfWork.open(phase6_factory) as unit:
        workflow = await unit.session.get(WorkflowRun, workflow_id)
        assert workflow is not None and workflow.status is WorkflowStatus.SAFE_STOPPED
        assert workflow.last_successful_stage == "A"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_parallel_failures_safe_stop_every_failing_stage(
    phase6_factory: async_sessionmaker[AsyncSession],
) -> None:
    workflow_id, a_id, b_id, _ = await running_workflow(phase6_factory)

    async def security_failure(_claim):
        raise SecurityViolationFailure("injected parallel security failure")

    async def transient_failure(_claim):
        raise AgentTransientError("injected parallel provider failure")

    scheduler = WorkflowScheduler(
        phase6_factory,
        recovery_graph(parallel=True),
        {"primary": security_failure, "descendant": transient_failure},
        scheduler_id="parallel-stop-test",
        max_parallel_stages=2,
    )
    result = await scheduler.run_cycle(workflow_id)

    assert [item.action for item in result.recovery] == [
        RecoveryAction.SAFE_STOPPED,
        RecoveryAction.SAFE_STOPPED,
    ]
    async with UnitOfWork.open(phase6_factory) as unit:
        workflow = await unit.session.get(WorkflowRun, workflow_id)
        stages = [await unit.session.get(StageRun, stage_id) for stage_id in (a_id, b_id)]
        assert workflow is not None and workflow.status is WorkflowStatus.SAFE_STOPPED
        assert all(
            stage is not None and stage.status is StageStatus.SAFE_STOPPED for stage in stages
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_only_human_can_resume_exact_latest_safe_stopped_attempt(
    phase6_factory: async_sessionmaker[AsyncSession],
) -> None:
    workflow_id, a_id, _, orchestrator = await running_workflow(phase6_factory)

    async def fail(_claim):
        raise SecurityViolationFailure("injected and then remediated")

    scheduler = WorkflowScheduler(
        phase6_factory,
        recovery_graph(),
        {"primary": fail},
        scheduler_id="resume-test",
    )
    await scheduler.run_cycle(workflow_id)
    async with UnitOfWork.open(phase6_factory) as unit:
        workflow = await unit.session.get(WorkflowRun, workflow_id)
        assert workflow is not None
        stopped_version = workflow.version

    with pytest.raises(InvalidTransitionError, match="human resolution"):
        await orchestrator.resume_safe_stopped(
            workflow_id,
            stage_run_id=a_id,
            resolution="remediated",
            context=TransitionContext(actor_type="SYSTEM", actor_id="not-human"),
        )
    await orchestrator.resume_safe_stopped(
        workflow_id,
        stage_run_id=a_id,
        resolution="Security finding remediated and lineage revalidated",
        context=TransitionContext(
            actor_type="HUMAN",
            actor_id="reviewer-1",
            expected_version=stopped_version,
        ),
    )

    async with UnitOfWork.open(phase6_factory) as unit:
        workflow = await unit.session.get(WorkflowRun, workflow_id)
        stages = list(
            await unit.session.scalars(
                select(StageRun)
                .where(StageRun.workflow_id == workflow_id, StageRun.stage_name == "A")
                .order_by(StageRun.attempt)
            )
        )
        events = await unit.audit.page(workflow_id)
        assert workflow is not None and workflow.status is WorkflowStatus.RUNNING
        assert [(stage.attempt, stage.status) for stage in stages] == [
            (1, StageStatus.SAFE_STOPPED),
            (2, StageStatus.PENDING),
        ]
        assert any(event.event_type == "STAGE_RECOVERY_APPROVED" for event in events)
