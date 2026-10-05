"""Human requirement updates and selective replanning API."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.api.dependencies import get_orchestrator
from app.api.workflows import schedule_workflow
from app.governance.auth import ReviewerIdentity, require_reviewer
from app.orchestration.commands import TransitionContext
from app.orchestration.contracts import WorkflowStatus
from app.orchestration.orchestrator import WorkflowOrchestrator
from app.orchestration.replanning import ReplanResult
from app.orchestration.state_machine import InvalidTransitionError, StaleTransitionError

router = APIRouter(prefix="/api/v1/workflows/{workflow_id}/requirements", tags=["requirements"])


def _to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(word.capitalize() for word in rest)


class RequirementUpdateRequest(BaseModel):
    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True, extra="forbid")

    requirement: str = Field(min_length=1, max_length=20_000)
    update_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    expected_workflow_version: int | None = Field(default=None, ge=1)
    reason: str | None = Field(default=None, max_length=2_000)


class RequirementUpdateResponse(BaseModel):
    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)

    workflow_id: uuid.UUID
    update_id: uuid.UUID
    workflow_status: WorkflowStatus
    workflow_version: int
    generation: int
    requirement_artifact_id: uuid.UUID
    requirement_version: int
    superseded_requirement_artifact_id: uuid.UUID
    stale_artifact_ids: tuple[uuid.UUID, ...]
    invalidated_approval_ids: tuple[uuid.UUID, ...]
    affected_stages: tuple[str, ...]
    current_stage: str
    architecture_approval_required: bool

    @classmethod
    def from_result(cls, result: ReplanResult) -> "RequirementUpdateResponse":
        return cls(**result.__dict__)


@router.post("", response_model=RequirementUpdateResponse, status_code=status.HTTP_201_CREATED)
async def update_requirement(
    workflow_id: uuid.UUID,
    body: RequirementUpdateRequest,
    request: Request,
    reviewer: Annotated[ReviewerIdentity, Depends(require_reviewer)],
    orchestrator: Annotated[WorkflowOrchestrator, Depends(get_orchestrator)],
) -> RequirementUpdateResponse:
    try:
        result = await orchestrator.update_requirement(
            workflow_id,
            requirement=body.requirement,
            update_id=body.update_id,
            context=TransitionContext(
                actor_type="HUMAN",
                actor_id=reviewer.reviewer_id,
                reason=body.reason,
                trace_id=uuid.UUID(request.state.trace_id),
                expected_version=body.expected_workflow_version,
            ),
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from None
    except (InvalidTransitionError, StaleTransitionError, ValueError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    schedule_workflow(request, workflow_id)
    return RequirementUpdateResponse.from_result(result)
