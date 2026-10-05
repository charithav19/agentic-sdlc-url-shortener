"""Typed human-approval contracts and safe public errors."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.orchestration.contracts import WorkflowStatus


class ApprovalType(StrEnum):
    ARCHITECTURE = "ARCHITECTURE"
    HIGH_IMPACT_CHANGE = "HIGH_IMPACT_CHANGE"
    ASSUMPTION = "ASSUMPTION"
    RELEASE = "RELEASE"


class ApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    INVALIDATED = "INVALIDATED"


class ApprovalDecision(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ApprovalError(RuntimeError):
    """Base class for errors safe to expose through the approval API."""


class ApprovalNotFoundError(ApprovalError):
    pass


class ApprovalConflictError(ApprovalError):
    pass


class StaleApprovalError(ApprovalConflictError):
    pass


@dataclass(frozen=True)
class ApprovalResult:
    approval_id: uuid.UUID
    workflow_id: uuid.UUID
    approval_type: ApprovalType
    status: ApprovalStatus
    artifact_id: uuid.UUID
    artifact_version: int
    artifact_hash: str
    reviewer_id: str | None
    reason: str | None
    decided_at: datetime | None
    workflow_status: WorkflowStatus
    workflow_version: int
