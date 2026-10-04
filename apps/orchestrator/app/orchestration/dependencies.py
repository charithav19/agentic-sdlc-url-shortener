"""Pure dependency resolver; gates and execution are separate later phases."""

from collections.abc import Mapping

from app.orchestration.contracts import StageStatus
from app.orchestration.graph import WorkflowGraph
from app.orchestration.readiness import StageReadiness, StageSnapshot

RECOMPUTABLE_STATUSES = frozenset({StageStatus.PENDING, StageStatus.BLOCKED, StageStatus.READY})


class StageDependencyResolver:
    def __init__(self, graph: WorkflowGraph) -> None:
        self.graph = graph

    def resolve(
        self,
        states: Mapping[str, StageSnapshot | StageStatus],
        *,
        generation: int = 1,
    ) -> dict[str, StageReadiness]:
        if generation < 1:
            raise ValueError("Generation must be positive")
        known = {stage.name for stage in self.graph.stages}
        unknown = set(states) - known
        if unknown:
            raise ValueError(f"Unknown stage states: {', '.join(sorted(unknown))}")

        current: dict[str, StageStatus] = {}
        for name, value in states.items():
            snapshot = (
                value
                if isinstance(value, StageSnapshot)
                else StageSnapshot(status=StageStatus(value), generation=generation)
            )
            if snapshot.generation == generation:
                current[name] = StageStatus(snapshot.status)

        decisions: dict[str, StageReadiness] = {}
        for name in self.graph.topological_order:
            stage = self.graph.stage(name)
            unmet = tuple(
                sorted(
                    dependency
                    for dependency in stage.dependencies
                    if current.get(dependency) != StageStatus.SUCCEEDED
                )
            )
            observed = current.get(name, StageStatus.PENDING)
            if observed in RECOMPUTABLE_STATUSES:
                status = StageStatus.BLOCKED if unmet else StageStatus.READY
            else:
                status = observed
            decisions[name] = StageReadiness(
                stage_name=name,
                status=status,
                unmet_dependencies=unmet,
            )
        return decisions
