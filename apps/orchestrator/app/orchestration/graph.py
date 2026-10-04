"""Typed immutable DAG configuration and deterministic validation."""

import hashlib
import heapq
import json
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from app.orchestration.registry import DEFAULT_REGISTRY, GraphRegistry


class GraphValidationError(ValueError):
    """The configured graph cannot be used as an executable DAG."""


class RetryPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    max_attempts: int = Field(ge=1, le=5)
    retryable_errors: tuple[str, ...]


class StageDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$", max_length=128)
    dependencies: tuple[str, ...]
    executor: str = Field(min_length=1)
    entry_gate: str = Field(min_length=1)
    exit_gate: str = Field(min_length=1)
    retry_policy: RetryPolicy
    fallback: str | None
    approval_required: bool


@dataclass(frozen=True)
class WorkflowGraph:
    version: str
    stages: tuple[StageDefinition, ...]
    sha256: str
    topological_order: tuple[str, ...]

    def stage(self, name: str) -> StageDefinition:
        for stage in self.stages:
            if stage.name == name:
                return stage
        raise KeyError(f"Unknown stage {name}")


def validate_graph(
    stages: tuple[StageDefinition, ...],
    *,
    registry: GraphRegistry = DEFAULT_REGISTRY,
) -> tuple[str, ...]:
    by_name: dict[str, StageDefinition] = {}
    for stage in stages:
        if stage.name in by_name:
            raise GraphValidationError(f"Duplicate stage name: {stage.name}")
        by_name[stage.name] = stage
        if stage.executor not in registry.executors:
            raise GraphValidationError(f"Unknown executor {stage.executor} for {stage.name}")
        for gate in (stage.entry_gate, stage.exit_gate):
            if gate not in registry.gates:
                raise GraphValidationError(f"Unknown gate {gate} for {stage.name}")
        if stage.fallback is not None:
            if stage.fallback not in registry.executors:
                raise GraphValidationError(f"Unknown fallback {stage.fallback} for {stage.name}")
            if stage.fallback == stage.executor:
                raise GraphValidationError(f"Fallback repeats primary executor for {stage.name}")
        unknown_errors = set(stage.retry_policy.retryable_errors) - registry.retryable_errors
        if unknown_errors:
            raise GraphValidationError(
                f"Unknown retryable errors for {stage.name}: {sorted(unknown_errors)}"
            )

    children: dict[str, list[str]] = {name: [] for name in by_name}
    remaining: dict[str, int] = {}
    for stage in stages:
        if len(stage.dependencies) != len(set(stage.dependencies)):
            raise GraphValidationError(f"Duplicate dependency in {stage.name}")
        for dependency in stage.dependencies:
            if dependency not in by_name:
                raise GraphValidationError(f"Unknown dependency {dependency} for {stage.name}")
            children[dependency].append(stage.name)
        remaining[stage.name] = len(stage.dependencies)

    ready = [name for name, count in remaining.items() if count == 0]
    heapq.heapify(ready)
    order: list[str] = []
    while ready:
        name = heapq.heappop(ready)
        order.append(name)
        for child in children[name]:
            remaining[child] -= 1
            if remaining[child] == 0:
                heapq.heappush(ready, child)
    if len(order) != len(stages):
        cyclic = sorted(name for name, count in remaining.items() if count > 0)
        raise GraphValidationError(f"Graph cycle involving: {', '.join(cyclic)}")
    return tuple(order)


def build_graph(
    version: str,
    stages: tuple[StageDefinition, ...],
    *,
    registry: GraphRegistry = DEFAULT_REGISTRY,
) -> WorkflowGraph:
    order = validate_graph(stages, registry=registry)
    normalized = []
    for stage in sorted(stages, key=lambda item: item.name):
        data = stage.model_dump(mode="json")
        data["dependencies"] = sorted(data["dependencies"])
        data["retry_policy"]["retryable_errors"] = sorted(data["retry_policy"]["retryable_errors"])
        normalized.append(data)
    canonical = json.dumps(
        {"version": version, "stages": normalized},
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return WorkflowGraph(version=version, stages=stages, sha256=digest, topological_order=order)
