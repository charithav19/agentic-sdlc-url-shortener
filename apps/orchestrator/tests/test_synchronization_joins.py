"""Mandatory synchronization waits for every required predecessor."""

import asyncio

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.orchestration.claims import StageClaim
from app.orchestration.contracts import StageStatus
from app.orchestration.graph_loader import load_graph
from app.orchestration.scheduler import WorkflowScheduler
from app.persistence.unit_of_work import UnitOfWork
from tests.test_parallel_execution import (
    add_stage,
    create_running_workflow,
    mark_succeeded,
)


@pytest.mark.integration
@pytest.mark.asyncio
async def _build_waits_for_delayed_test_design_then_becomes_ready(
    phase6_factory: async_sessionmaker[AsyncSession],
) -> None:
    workflow_id, persistence, orchestrator = await create_running_workflow(
        phase6_factory, "mandatory-build-join"
    )
    architecture_approval_id = await add_stage(
        persistence, workflow_id, "ARCHITECTURE_APPROVAL", "human_checkpoint"
    )
    await mark_succeeded(orchestrator, architecture_approval_id)
    implementation_id = await add_stage(
        persistence, workflow_id, "IMPLEMENTATION", "implementation_specialist"
    )
    test_design_id = await add_stage(
        persistence, workflow_id, "TEST_DESIGN", "test_design_specialist"
    )
    await add_stage(persistence, workflow_id, "DOCUMENTATION_DRAFT", "documentation_specialist")
    build_id = await add_stage(persistence, workflow_id, "BUILD_VALIDATION", "build_runner")

    implementation_done = asyncio.Event()
    test_design_started = asyncio.Event()
    release_test_design = asyncio.Event()

    async def implementation(_claim: StageClaim) -> dict:
        implementation_done.set()
        return {"implementation": "complete"}

    async def test_design(_claim: StageClaim) -> dict:
        test_design_started.set()
        await release_test_design.wait()
        return {"testDesign": "complete"}

    async def documentation(_claim: StageClaim) -> dict:
        return {"documentation": "drafted"}

    scheduler = WorkflowScheduler(
        phase6_factory,
        load_graph(),
        {
            "implementation_specialist": implementation,
            "test_design_specialist": test_design,
            "documentation_specialist": documentation,
        },
        max_parallel_stages=3,
        scheduler_id="join-scheduler",
    )
    cycle = asyncio.create_task(scheduler.run_cycle(workflow_id))
    await asyncio.wait_for(implementation_done.wait(), timeout=2)
    await asyncio.wait_for(test_design_started.wait(), timeout=2)

    for _ in range(40):
        async with UnitOfWork.open(phase6_factory) as unit:
            implementation_stage = await unit.stages.get(implementation_id)
            test_design_stage = await unit.stages.get(test_design_id)
            build_stage = await unit.stages.get(build_id)
            if implementation_stage.status is StageStatus.SUCCEEDED:
                break
        await asyncio.sleep(0.01)
    assert implementation_stage.status is StageStatus.SUCCEEDED
    assert test_design_stage.status is StageStatus.RUNNING
    assert build_stage.status is StageStatus.BLOCKED

    release_test_design.set()
    await asyncio.wait_for(cycle, timeout=2)

    async with UnitOfWork.open(phase6_factory) as unit:
        test_design_stage = await unit.stages.get(test_design_id)
        build_stage = await unit.stages.get(build_id)
        events = await unit.audit.page(workflow_id)
        build_events = [
            event
            for event in events
            if event.stage_run_id == build_id and event.event_type == "STAGE_READINESS_CHANGED"
        ]
        assert test_design_stage.status is StageStatus.SUCCEEDED
        assert build_stage.status is StageStatus.READY
        assert [(event.before_state, event.after_state) for event in build_events] == [
            (StageStatus.PENDING.value, StageStatus.BLOCKED.value),
            (StageStatus.BLOCKED.value, StageStatus.READY.value),
        ]
        assert all(event.event_type == "STAGE_READINESS_CHANGED" for event in build_events)
        assert any(event.event_type == "STAGE_CLAIMED" for event in events)
        assert any(event.event_type == "STAGE_CLAIM_COMPLETED" for event in events)


@pytest.mark.integration
@pytest.mark.asyncio
class ParallelJoinScenarioIT:
    async def test_build_waits_for_every_required_parallel_predecessor(
        self, phase6_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await _build_waits_for_delayed_test_design_then_becomes_ready(phase6_factory)
