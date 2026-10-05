"""Authenticated human recovery for safe-stopped workflows."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.api.dependencies import get_orchestrator
from app.governance.auth import ReviewerIdentity, require_reviewer
from app.orchestration.commands import TransitionContext
from app.orchestration.contracts import WorkflowStatus
from app.orchestration.orchestrator import WorkflowOrchestrator
from app.orchestration.state_machine import InvalidTransitionError, StaleTransitionError

router = APIRouter(prefix="/api/v1/workflows/{workflow_id}", tags=["recovery"])


def _to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(word.capitalize() for word in rest)


class ResumeRequest(BaseModel):
    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True, extra="forbid")

    stage_run_id: uuid.UUID
    workflow_version: int = Field(ge=1)
    cause_resolved: Literal[True]
    resolution: str = Field(min_length=1, max_length=2000)


class ResumeResponse(BaseModel):
    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)

    workflow_id: uuid.UUID
    stage_run_id: uuid.UUID
    status: WorkflowStatus
    workflow_version: int


@router.post("/resume", response_model=ResumeResponse)
async def resume_workflow(
    workflow_id: uuid.UUID,
    body: ResumeRequest,
    request: Request,
    reviewer: Annotated[ReviewerIdentity, Depends(require_reviewer)],
    orchestrator: Annotated[WorkflowOrchestrator, Depends(get_orchestrator)],
) -> ResumeResponse:
    try:
        result = await orchestrator.resume_safe_stopped(
            workflow_id,
            stage_run_id=body.stage_run_id,
            resolution=body.resolution,
            context=TransitionContext(
                actor_type="HUMAN",
                actor_id=reviewer.reviewer_id,
                reason=body.resolution,
                trace_id=uuid.UUID(request.state.trace_id),
                expected_version=body.workflow_version,
            ),
        )
    except KeyError:
        raise HTTPException(
            status_code=404, detail="Workflow or stopped stage was not found"
        ) from None
    except (InvalidTransitionError, StaleTransitionError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    return ResumeResponse(
        workflow_id=workflow_id,
        stage_run_id=body.stage_run_id,
        status=WorkflowStatus.RUNNING,
        workflow_version=result.version,
    )
