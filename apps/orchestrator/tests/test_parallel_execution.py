"""Bounded stage concurrency and durable exclusive claims."""

import asyncio
import uuid
from collections.abc import Sequence

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.orchestration.claims import StageClaim
from app.orchestration.commands import TransitionContext
from app.orchestration.contracts import ScenarioType, StageStatus, WorkflowStatus
from app.orchestration.graph_loader import load_graph
from app.orchestration.orchestrator import WorkflowOrchestrator
from app.orchestration.scheduler import WorkflowScheduler
from app.persistence.models import StageRun
from app.persistence.service import WorkflowPersistenceService
from app.persistence.unit_of_work import UnitOfWork

StageSpec = tuple[str, str]


async def create_running_workflow(
    factory: async_sessionmaker[AsyncSession], label: str
) -> tuple[uuid.UUID, WorkflowPersistenceService, WorkflowOrchestrator]:
    persistence = WorkflowPersistenceService(factory)
    orchestrator = WorkflowOrchestrator(factory)
    workflow_id = await persistence.create_workflow(
        scenario_type=ScenarioType.GREENFIELD,
        provider_mode="fake",
        workspace_ref=label,
    )
    await orchestrator.transition_workflow(
        workflow_id,
        WorkflowStatus.RUNNING,
        TransitionContext(actor_type="SYSTEM", actor_id="test-scheduler"),
    )
    return workflow_id, persistence, orchestrator


async def add_stage(
    persistence: WorkflowPersistenceService,
    workflow_id: uuid.UUID,
    stage_name: str,
    executor: str,
) -> uuid.UUID:
    return await persistence.add_stage_attempt(
        workflow_id,
        stage_name=stage_name,
        generation=1,
        attempt=1,
        executor=executor,
    )


async def mark_succeeded(orchestrator: WorkflowOrchestrator, stage_id: uuid.UUID) -> None:
    context = TransitionContext(actor_type="SYSTEM", actor_id="test-scheduler")
    for status in (StageStatus.READY, StageStatus.RUNNING, StageStatus.SUCCEEDED):
        await orchestrator.transition_stage(stage_id, status, context)


async def stage_statuses(
    factory: async_sessionmaker[AsyncSession], stage_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, StageStatus]:
    async with UnitOfWork.open(factory) as unit:
        return {stage_id: (await unit.stages.get(stage_id)).status for stage_id in stage_ids}


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("predecessor", "predecessor_executor", "children"),
    [
        (
            "ARCHITECTURE_APPROVAL",
            "human_checkpoint",
            (
                ("IMPLEMENTATION", "implementation_specialist"),
                ("TEST_DESIGN", "test_design_specialist"),
                ("DOCUMENTATION_DRAFT", "documentation_specialist"),
            ),
        ),
        (
            "BUILD_VALIDATION",
            "build_runner",
            (
                ("UNIT_TEST", "unit_test_runner"),
                ("INTEGRATION_TEST", "integration_test_runner"),
                ("SECURITY_VALIDATION", "security_specialist"),
            ),
        ),
    ],
)
async def test_configured_fan_outs_execute_concurrently(
    phase6_factory: async_sessionmaker[AsyncSession],
    predecessor: str,
    predecessor_executor: str,
    children: tuple[StageSpec, ...],
) -> None:
    workflow_id, persistence, orchestrator = await create_running_workflow(
        phase6_factory, f"parallel-{predecessor.lower()}"
    )
    predecessor_id = await add_stage(persistence, workflow_id, predecessor, predecessor_executor)
    await mark_succeeded(orchestrator, predecessor_id)
    child_ids = {
        name: await add_stage(persistence, workflow_id, name, executor)
        for name, executor in children
    }

    started: set[str] = set()
    all_started = asyncio.Event()
    release = asyncio.Event()

    async def barrier_executor(claim: StageClaim) -> dict:
        started.add(claim.stage_name)
        if len(started) == len(children):
            all_started.set()
        await release.wait()
        return {"stage": claim.stage_name}

    scheduler = WorkflowScheduler(
        phase6_factory,
        load_graph(),
        {executor: barrier_executor for _, executor in children},
        max_parallel_stages=3,
        scheduler_id=f"scheduler-{predecessor.lower()}",
    )
    cycle = asyncio.create_task(scheduler.run_cycle(workflow_id))
    await asyncio.wait_for(all_started.wait(), timeout=2)

    assert started == set(child_ids)
    assert not cycle.done()
    running = await stage_statuses(phase6_factory, tuple(child_ids.values()))
    assert set(running.values()) == {StageStatus.RUNNING}

    release.set()
    result = await asyncio.wait_for(cycle, timeout=2)
    assert len(result.work) == 3
    assert all(item.claimed and item.committed and item.succeeded for item in result.work)
    completed = await stage_statuses(phase6_factory, tuple(child_ids.values()))
    assert set(completed.values()) == {StageStatus.SUCCEEDED}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_scheduler_never_exceeds_configured_concurrency(
    phase6_factory: async_sessionmaker[AsyncSession],
) -> None:
    workflow_id, persistence, orchestrator = await create_running_workflow(
        phase6_factory, "parallel-bound"
    )
    predecessor_id = await add_stage(
        persistence, workflow_id, "ARCHITECTURE_APPROVAL", "human_checkpoint"
    )
    await mark_succeeded(orchestrator, predecessor_id)
    children: tuple[StageSpec, ...] = (
        ("IMPLEMENTATION", "implementation_specialist"),
        ("TEST_DESIGN", "test_design_specialist"),
        ("DOCUMENTATION_DRAFT", "documentation_specialist"),
    )
    for name, executor in children:
        await add_stage(persistence, workflow_id, name, executor)

    active = 0
    maximum = 0

    async def measured_executor(_claim: StageClaim) -> dict:
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        await asyncio.sleep(0.03)
        active -= 1
        return {"ok": True}

    scheduler = WorkflowScheduler(
        phase6_factory,
        load_graph(),
        {executor: measured_executor for _, executor in children},
        max_parallel_stages=2,
        scheduler_id="bounded-scheduler",
    )
    await scheduler.run_cycle(workflow_id)
    assert maximum == 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_competing_schedulers_cannot_duplicate_a_stage_claim(
    phase6_factory: async_sessionmaker[AsyncSession],
) -> None:
    workflow_id, persistence, orchestrator = await create_running_workflow(
        phase6_factory, "duplicate-claim"
    )
    stage_id = await add_stage(persistence, workflow_id, "INTAKE", "intake")
    await orchestrator.transition_stage(
        stage_id,
        StageStatus.READY,
        TransitionContext(actor_type="SYSTEM", actor_id="test-scheduler"),
    )

    calls = 0
    started = asyncio.Event()
    release = asyncio.Event()

    async def one_execution(_claim: StageClaim) -> dict:
        nonlocal calls
        calls += 1
        started.set()
        await release.wait()
        return {"calls": calls}

    schedulers = (
        WorkflowScheduler(
            phase6_factory,
            load_graph(),
            {"intake": one_execution},
            scheduler_id="scheduler-a",
        ),
        WorkflowScheduler(
            phase6_factory,
            load_graph(),
            {"intake": one_execution},
            scheduler_id="scheduler-b",
        ),
    )
    tasks = [asyncio.create_task(item.run_cycle(workflow_id)) for item in schedulers]
    await asyncio.wait_for(started.wait(), timeout=2)
    await asyncio.sleep(0.05)
    release.set()
    results = await asyncio.gather(*tasks)

    assert calls == 1
    attempts = [work for result in results for work in result.work]
    assert sum(item.claimed for item in attempts) == 1
    async with UnitOfWork.open(phase6_factory) as unit:
        stage = await unit.session.get(StageRun, stage_id)
        events = await unit.audit.page(workflow_id)
        assert stage is not None and stage.status is StageStatus.SUCCEEDED
        assert sum(event.event_type == "STAGE_CLAIMED" for event in events) == 1
        assert sum(event.event_type == "STAGE_CLAIM_COMPLETED" for event in events) == 1
