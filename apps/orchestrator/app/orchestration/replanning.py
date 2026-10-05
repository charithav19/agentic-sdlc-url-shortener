"""Deterministic stage impact planning for requirement revisions."""

import uuid
from dataclasses import dataclass

from app.orchestration.contracts import WorkflowStatus
from app.orchestration.graph import WorkflowGraph


@dataclass(frozen=True)
class ReplanResult:
    workflow_id: uuid.UUID
    update_id: uuid.UUID
    workflow_status: WorkflowStatus
    workflow_version: int
    generation: int
    requirement_artifact_id: uuid.UUID
    requirement_version: int
    superseded_requirement_artifact_id: uuid.UUID
    stale_artifact_ids: tuple[uuid.UUID, ...]
    invalidated_approval_ids: tuple[uuid.UUID, ...]
    affected_stages: tuple[str, ...]
    current_stage: str
    architecture_approval_required: bool


class SelectiveReplanPlanner:
    """Expand artifact-producing stages through the configured DAG."""

    _REQUIRED_REPLAN_STAGES = frozenset(
        {"TASK_DECOMPOSITION", "ARCHITECTURE_DESIGN", "ARCHITECTURE_APPROVAL"}
    )

    def __init__(self, graph: WorkflowGraph) -> None:
        self.graph = graph

    def affected_stages(self, producer_stage_names: set[str]) -> tuple[str, ...]:
        known = set(self.graph.topological_order)
        affected = (producer_stage_names & known) | self._REQUIRED_REPLAN_STAGES
        changed = True
        while changed:
            changed = False
            for stage in self.graph.stages:
                if stage.name not in affected and any(
                    dependency in affected for dependency in stage.dependencies
                ):
                    affected.add(stage.name)
                    changed = True
        # Intake and analysis are fulfilled by preserved intake plus the human
        # requirement update. Every later affected stage receives a fresh run.
        affected.discard("INTAKE")
        affected.discard("REQUIREMENT_ANALYSIS")
        return tuple(name for name in self.graph.topological_order if name in affected)
