"""Exclusive stage-claim contracts used by the deterministic scheduler."""

import uuid
from dataclasses import dataclass
from datetime import datetime


class ClaimUnavailableError(RuntimeError):
    """The stage is not currently eligible for an exclusive claim."""


class StaleClaimError(RuntimeError):
    """A worker attempted to commit with an obsolete fencing token."""


@dataclass(frozen=True)
class StageClaim:
    stage_run_id: uuid.UUID
    workflow_id: uuid.UUID
    stage_name: str
    executor: str
    generation: int
    attempt: int
    execution_mode: str
    token: uuid.UUID
    owner: str
    lease_expires_at: datetime


@dataclass(frozen=True)
class StageCompletion:
    stage_run_id: uuid.UUID
    stage_name: str
    succeeded: bool
    version: int
