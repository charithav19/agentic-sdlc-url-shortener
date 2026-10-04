"""Agent invocation cannot mutate durable workflow or stage state."""

import pytest

from app.agents.registry import SPECIALISTS
from app.orchestration.contracts import ScenarioType, StageStatus, WorkflowStatus
from app.persistence.service import WorkflowPersistenceService
from app.persistence.unit_of_work import UnitOfWork


@pytest.mark.integration
@pytest.mark.asyncio
async def test_specialists_leave_state_and_audit_unchanged(
    phase6_factory, agent_context, agent_provider
):
    persistence = WorkflowPersistenceService(phase6_factory)
    workflow_id = await persistence.create_workflow(
        scenario_type=ScenarioType.GREENFIELD, provider_mode="fake", workspace_ref="agent-boundary"
    )
    stage_id = await persistence.add_stage_attempt(
        workflow_id,
        stage_name="REQUIREMENT_ANALYSIS",
        generation=1,
        attempt=1,
        executor="requirements_specialist",
    )
    async with UnitOfWork.open(phase6_factory) as unit:
        before_events = [event.id for event in await unit.audit.page(workflow_id)]
    context = agent_context.model_copy(
        update={"workflow_id": workflow_id, "stage_run_id": stage_id}
    )
    for specialist in SPECIALISTS.values():
        await agent_provider.run(specialist, context)
    async with UnitOfWork.open(phase6_factory) as unit:
        workflow = await unit.workflows.get(workflow_id)
        stage = await unit.stages.get(stage_id)
        assert (workflow.status, workflow.version) == (WorkflowStatus.CREATED, 1)
        assert (stage.status, stage.version) == (StageStatus.PENDING, 1)
        assert [event.id for event in await unit.audit.page(workflow_id)] == before_events
