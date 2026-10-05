import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.errors import AgentTransientError
from app.orchestration.contracts import StageStatus, WorkflowStatus
from app.orchestration.recovery import RecoveryAction
from app.orchestration.retries import RetryPlanner
from app.orchestration.scheduler import WorkflowScheduler
from app.persistence.models import StageRun, WorkflowRun
from app.persistence.unit_of_work import UnitOfWork
from tests.recovery_fixtures import recovery_graph, running_workflow


@pytest.mark.integration
@pytest.mark.asyncio
async def _real_provider_exhaustion_uses_deterministic_fallback(
    phase6_factory: async_sessionmaker[AsyncSession],
) -> None:
    workflow_id, _, _, _ = await running_workflow(phase6_factory)
    primary_calls = 0
    fallback_calls = 0

    async def real_provider(_claim):
        nonlocal primary_calls
        primary_calls += 1
        raise AgentTransientError("injected OpenAI provider outage")

    async def deterministic_fallback(claim):
        nonlocal fallback_calls
        fallback_calls += 1
        assert claim.execution_mode == "FALLBACK"
        return {"provider": "deterministic", "fixture": True}

    scheduler = WorkflowScheduler(
        phase6_factory,
        recovery_graph(fallback="deterministic_fallback"),
        {"primary": real_provider, "deterministic_fallback": deterministic_fallback},
        scheduler_id="fallback-test",
        retry_planner=RetryPlanner(base_delay_seconds=0, maximum_delay_seconds=0),
    )
    await scheduler.run_cycle(workflow_id)
    exhausted = await scheduler.run_cycle(workflow_id)
    fallback = await scheduler.run_cycle(workflow_id)

    assert exhausted.recovery[0].action is RecoveryAction.FALLBACK_SCHEDULED
    assert fallback.work[0].succeeded is True
    assert primary_calls == 2
    assert fallback_calls == 1
    async with UnitOfWork.open(phase6_factory) as unit:
        workflow = await unit.session.get(WorkflowRun, workflow_id)
        attempts = list(
            await unit.session.scalars(
                select(StageRun)
                .where(StageRun.workflow_id == workflow_id, StageRun.stage_name == "A")
                .order_by(StageRun.attempt)
            )
        )
        events = await unit.audit.page(workflow_id)
        assert workflow is not None and workflow.status is WorkflowStatus.RUNNING
        assert [row.attempt for row in attempts] == [1, 2, 3]
        assert attempts[-1].execution_mode == "FALLBACK"
        assert attempts[-1].fallback_source_stage_run_id == attempts[1].id
        assert attempts[-1].status is StageStatus.SUCCEEDED
        assert any(event.event_type == "STAGE_FALLBACK_SCHEDULED" for event in events)


@pytest.mark.integration
@pytest.mark.asyncio
class FailureRecoveryScenarioIT:
    async def test_retry_exhaustion_recovers_through_deterministic_fallback(
        self, phase6_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await _real_provider_exhaustion_uses_deterministic_fallback(phase6_factory)
