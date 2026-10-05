"""Fallback selection is explicit in the versioned stage definition."""

from dataclasses import dataclass

from app.orchestration.graph import StageDefinition


@dataclass(frozen=True)
class FallbackPlan:
    executor: str
    source_attempt: int


def fallback_after_exhaustion(
    definition: StageDefinition, *, source_attempt: int, execution_mode: str
) -> FallbackPlan | None:
    if execution_mode != "PRIMARY" or definition.fallback is None:
        return None
    return FallbackPlan(executor=definition.fallback, source_attempt=source_attempt)
