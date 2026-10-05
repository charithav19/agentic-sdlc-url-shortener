from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.errors import AgentTimeout, AgentTransientError
from app.orchestration.contracts import StageStatus, WorkflowStatus
from app.orchestration.recovery import RecoveryAction
from app.orchestration.retries import DEFAULT_MAX_ATTEMPTS, RetryPlanner
from app.orchestration.scheduler import WorkflowScheduler
from app.persistence.models import StageRun, WorkflowRun
from app.persistence.unit_of_work import UnitOfWork
from tests.recovery_fixtures import recovery_graph, running_workflow


def test_default_attempt_limit_and_bounded_deterministic_backoff() -> None:
    assert DEFAULT_MAX_ATTEMPTS == 2
    now = datetime(2026, 1, 1, tzinfo=UTC)
    planner = RetryPlanner(base_delay_seconds=4, maximum_delay_seconds=5, jitter_ratio=0.5)
    first = planner.schedule(completed_attempt=1, now=now, jitter_fraction=0.5)
    later = planner.schedule(completed_attempt=5, now=now, jitter_fraction=1)
    assert first.next_attempt == 2
    assert first.delay_seconds == 5
    assert later.delay_seconds == 5


@pytest.mark.integration
@pytest.mark.asyncio
async def test_temporary_failure_retries_once_and_preserves_both_attempts(
    phase6_factory: async_sessionmaker[AsyncSession],
) -> None:
    workflow_id, _, b_id, _ = await running_workflow(phase6_factory)
    calls = 0

    async def flaky(_claim):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise AgentTimeout("injected timeout")
        return {"attempt": calls}

    scheduler = WorkflowScheduler(
        phase6_factory,
        recovery_graph(),
        {"primary": flaky},
        scheduler_id="retry-test",
        retry_planner=RetryPlanner(base_delay_seconds=0, maximum_delay_seconds=0),
    )
    first = await scheduler.run_cycle(workflow_id)
    second = await scheduler.run_cycle(workflow_id)

    assert first.recovery[0].action is RecoveryAction.RETRY_SCHEDULED
    assert second.work[0].succeeded is True
    assert calls == DEFAULT_MAX_ATTEMPTS
    async with UnitOfWork.open(phase6_factory) as unit:
        attempts = list(
            await unit.session.scalars(
                select(StageRun)
                .where(StageRun.workflow_id == workflow_id, StageRun.stage_name == "A")
                .order_by(StageRun.attempt)
            )
        )
        descendant = await unit.session.get(StageRun, b_id)
        assert [(row.attempt, row.status) for row in attempts] == [
            (1, StageStatus.RETRY_PENDING),
            (2, StageStatus.SUCCEEDED),
        ]
        assert attempts[0].failure_code == "OPENAI_TIMEOUT"
        assert attempts[0].error_message == "AgentTimeout: injected timeout"
        assert descendant is not None and descendant.status is StageStatus.READY


@pytest.mark.integration
@pytest.mark.asyncio
async def test_retry_exhaustion_without_fallback_safe_stops(
    phase6_factory: async_sessionmaker[AsyncSession],
) -> None:
    workflow_id, _, b_id, _ = await running_workflow(phase6_factory)

    async def unavailable(_claim):
        raise AgentTransientError("injected provider outage")

    scheduler = WorkflowScheduler(
        phase6_factory,
        recovery_graph(),
        {"primary": unavailable},
        scheduler_id="exhaustion-test",
        retry_planner=RetryPlanner(base_delay_seconds=0, maximum_delay_seconds=0),
    )
    await scheduler.run_cycle(workflow_id)
    exhausted = await scheduler.run_cycle(workflow_id)
    no_more_work = await scheduler.run_cycle(workflow_id)

    assert exhausted.recovery[0].action is RecoveryAction.SAFE_STOPPED
    assert no_more_work.work == ()
    async with UnitOfWork.open(phase6_factory) as unit:
        workflow = await unit.session.get(WorkflowRun, workflow_id)
        attempts = list(
            await unit.session.scalars(
                select(StageRun)
                .where(StageRun.workflow_id == workflow_id, StageRun.stage_name == "A")
                .order_by(StageRun.attempt)
            )
        )
        descendant = await unit.session.get(StageRun, b_id)
        assert workflow is not None and workflow.status is WorkflowStatus.SAFE_STOPPED
        assert [row.attempt for row in attempts] == [1, 2]
        assert attempts[-1].status is StageStatus.SAFE_STOPPED
        assert descendant is not None and descendant.status is StageStatus.BLOCKED
