"""Mandatory fan-in synchronization over the configured workflow DAG."""

import uuid
from dataclasses import dataclass

from app.orchestration.commands import TransitionContext
from app.orchestration.graph import WorkflowGraph
from app.orchestration.orchestrator import WorkflowOrchestrator
from app.orchestration.readiness import ReadinessChange


@dataclass(frozen=True)
class SynchronizationResult:
    workflow_id: uuid.UUID
    changes: tuple[ReadinessChange, ...]


class SynchronizationJoinCoordinator:
    """Apply mandatory dependency joins without interpreting partial success as success."""

    def __init__(self, graph: WorkflowGraph, orchestrator: WorkflowOrchestrator) -> None:
        self.graph = graph
        self.orchestrator = orchestrator

    async def synchronize(
        self, workflow_id: uuid.UUID, *, actor_id: str, trace_id: uuid.UUID | None = None
    ) -> SynchronizationResult:
        changes = await self.orchestrator.synchronize_stage_readiness(
            workflow_id,
            self.graph,
            TransitionContext(
                actor_type="SYSTEM",
                actor_id=actor_id,
                trace_id=trace_id,
                reason="Recompute mandatory dependency joins",
            ),
        )
        return SynchronizationResult(workflow_id=workflow_id, changes=changes)
