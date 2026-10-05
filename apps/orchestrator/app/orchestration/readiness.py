"""Immutable structural readiness results for one graph generation."""

import uuid
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


@dataclass(frozen=True)
class ReadinessChange:
    stage_run_id: uuid.UUID
    stage_name: str
    previous_status: StageStatus
    current_status: StageStatus
    unmet_dependencies: tuple[str, ...]
