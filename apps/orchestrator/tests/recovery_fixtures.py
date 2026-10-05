import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.orchestration.commands import TransitionContext
from app.orchestration.contracts import ScenarioType, StageStatus, WorkflowStatus
from app.orchestration.graph import RetryPolicy, StageDefinition, WorkflowGraph, build_graph
from app.orchestration.orchestrator import WorkflowOrchestrator
from app.orchestration.registry import GraphRegistry
from app.persistence.service import WorkflowPersistenceService


def recovery_graph(
    *, fallback: str | None = None, max_attempts: int = 2, parallel: bool = False
) -> WorkflowGraph:
    stages = (
        StageDefinition(
            name="A",
            dependencies=(),
            executor="primary",
            entry_gate="always",
            exit_gate="done",
            retry_policy=RetryPolicy(max_attempts=max_attempts),
            fallback=fallback,
            approval_required=False,
        ),
        StageDefinition(
            name="B",
            dependencies=() if parallel else ("A",),
            executor="descendant",
            entry_gate="always",
            exit_gate="done",
            retry_policy=RetryPolicy(max_attempts=2),
            fallback=None,
            approval_required=False,
        ),
    )
    registry = GraphRegistry(
        executors=frozenset({"primary", "descendant", "deterministic_fallback"}),
        gates=frozenset({"always", "done"}),
        retryable_errors=frozenset(),
    )
    return build_graph("recovery-test", stages, registry=registry)


async def running_workflow(
    factory: async_sessionmaker[AsyncSession],
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, WorkflowOrchestrator]:
    persistence = WorkflowPersistenceService(factory)
    orchestrator = WorkflowOrchestrator(factory)
    workflow_id = await persistence.create_workflow(
        scenario_type=ScenarioType.GREENFIELD,
        provider_mode="fake",
        workspace_ref=f"recovery-{uuid.uuid4()}",
    )
    a_id = await persistence.add_stage_attempt(
        workflow_id,
        stage_name="A",
        generation=1,
        attempt=1,
        executor="primary",
    )
    b_id = await persistence.add_stage_attempt(
        workflow_id,
        stage_name="B",
        generation=1,
        attempt=1,
        executor="descendant",
    )
    await orchestrator.transition_workflow(
        workflow_id,
        WorkflowStatus.RUNNING,
        TransitionContext(actor_type="SYSTEM", actor_id="recovery-test"),
    )
    return workflow_id, a_id, b_id, orchestrator


async def set_stage_succeeded(orchestrator: WorkflowOrchestrator, stage_id: uuid.UUID) -> None:
    context = TransitionContext(actor_type="SYSTEM", actor_id="recovery-test")
    for status in (StageStatus.READY, StageStatus.RUNNING, StageStatus.SUCCEEDED):
        await orchestrator.transition_stage(stage_id, status, context)
