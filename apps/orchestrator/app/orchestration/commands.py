"""Validated state-transition command context."""

import uuid
from dataclasses import dataclass
from typing import Literal

ActorType = Literal["SYSTEM", "HUMAN"]


@dataclass(frozen=True)
class TransitionContext:
    actor_type: ActorType
    actor_id: str
    reason: str | None = None
    trace_id: uuid.UUID | None = None
    expected_version: int | None = None

    def __post_init__(self) -> None:
        if self.actor_type not in ("SYSTEM", "HUMAN"):
            raise ValueError("Only SYSTEM or HUMAN may request a state transition")
        if not self.actor_id.strip():
            raise ValueError("Transition actor_id is required")
        if self.expected_version is not None and self.expected_version < 1:
            raise ValueError("expected_version must be positive")
