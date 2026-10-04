"""Immutable structural readiness results for one graph generation."""

from dataclasses import dataclass

from app.orchestration.contracts import StageStatus


@dataclass(frozen=True)
class StageSnapshot:
    status: StageStatus
    generation: int


@dataclass(frozen=True)
class StageReadiness:
    stage_name: str
    status: StageStatus
    unmet_dependencies: tuple[str, ...]
