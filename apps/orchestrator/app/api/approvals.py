"""Human approval decision API."""

import uuid
from datetime import datetime
from typing import Annotated, Self

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.api.dependencies import get_orchestrator
from app.api.workflows import schedule_workflow
from app.governance.approvals import (
    ApprovalConflictError,
    ApprovalDecision,
    ApprovalNotFoundError,
    ApprovalResult,
    ApprovalStatus,
    ApprovalType,
)
from app.governance.auth import ReviewerIdentity, require_reviewer
from app.orchestration.commands import TransitionContext
from app.orchestration.contracts import WorkflowStatus
from app.orchestration.orchestrator import WorkflowOrchestrator
from app.orchestration.state_machine import InvalidTransitionError, StaleTransitionError

router = APIRouter(prefix="/api/v1/workflows/{workflow_id}/approvals", tags=["approvals"])


def _to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(word.capitalize() for word in rest)


class ApprovalDecisionRequest(BaseModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        extra="forbid",
    )

    approval_id: uuid.UUID
    artifact_id: uuid.UUID
    artifact_version: int = Field(ge=1)
    status: ApprovalDecision
    reason: str | None = Field(default=None, max_length=2000)
    workflow_version: int = Field(ge=1)

    @model_validator(mode="after")
    def require_rejection_reason(self) -> Self:
        if self.status is ApprovalDecision.REJECTED and (
            self.reason is None or not self.reason.strip()
        ):
            raise ValueError("A rejection reason is required")
        return self


class ApprovalResponse(BaseModel):
    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)

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

    @classmethod
    def from_result(cls, result: ApprovalResult) -> "ApprovalResponse":
        return cls(**result.__dict__)


@router.post("", response_model=ApprovalResponse, status_code=status.HTTP_200_OK)
async def submit_approval_decision(
    workflow_id: uuid.UUID,
    body: ApprovalDecisionRequest,
    request: Request,
    reviewer: Annotated[ReviewerIdentity, Depends(require_reviewer)],
    orchestrator: Annotated[WorkflowOrchestrator, Depends(get_orchestrator)],
) -> ApprovalResponse:
    try:
        trace_id = uuid.UUID(request.state.trace_id)
        result = await orchestrator.decide_approval(
            workflow_id,
            approval_id=body.approval_id,
            artifact_id=body.artifact_id,
            artifact_version=body.artifact_version,
            decision=body.status,
            reviewer_id=reviewer.reviewer_id,
            reason=body.reason,
            context=TransitionContext(
                actor_type="HUMAN",
                actor_id=reviewer.reviewer_id,
                reason=body.reason,
                trace_id=trace_id,
                expected_version=body.workflow_version,
            ),
        )
    except (KeyError, ApprovalNotFoundError):
        raise HTTPException(status_code=404, detail="Workflow or approval was not found") from None
    except (ApprovalConflictError, InvalidTransitionError, StaleTransitionError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    schedule_workflow(request, workflow_id)
    return ApprovalResponse.from_result(result)
