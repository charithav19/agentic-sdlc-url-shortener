"""Human clarification submission API."""

import uuid
from typing import Annotated, Self

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.api.dependencies import get_orchestrator
from app.governance.auth import ReviewerIdentity, require_reviewer
from app.orchestration.clarifications import ClarificationSubmissionResult
from app.orchestration.commands import TransitionContext
from app.orchestration.contracts import WorkflowStatus
from app.orchestration.orchestrator import WorkflowOrchestrator
from app.orchestration.state_machine import InvalidTransitionError, StaleTransitionError

router = APIRouter(prefix="/api/v1/workflows/{workflow_id}/clarifications", tags=["clarifications"])


def _to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(word.capitalize() for word in rest)


class ClarificationAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=2_000)
    answer: str = Field(min_length=1, max_length=8_000)


class ClarificationSubmissionRequest(BaseModel):
    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True, extra="forbid")

    clarification_artifact_id: uuid.UUID
    clarification_artifact_version: int = Field(ge=1)
    answers: tuple[ClarificationAnswer, ...] = Field(min_length=1, max_length=50)
    expected_workflow_version: int | None = Field(default=None, ge=1)
    reason: str | None = Field(default=None, max_length=2_000)

    @model_validator(mode="after")
    def unique_questions(self) -> Self:
        normalized = [item.question.strip() for item in self.answers]
        if len(set(normalized)) != len(normalized):
            raise ValueError("Clarification questions must be unique")
        return self


class ClarificationSubmissionResponse(BaseModel):
    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)

    workflow_id: uuid.UUID
    workflow_status: WorkflowStatus
    workflow_version: int
    generation: int
    clarification_artifact_id: uuid.UUID
    clarification_artifact_version: int
    requirement_artifact_id: uuid.UUID
    requirement_version: int
    requirement_analysis_stage_run_id: uuid.UUID

    @classmethod
    def from_result(
        cls, result: ClarificationSubmissionResult
    ) -> "ClarificationSubmissionResponse":
        return cls(**result.__dict__)


@router.post(
    "",
    response_model=ClarificationSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_clarification(
    workflow_id: uuid.UUID,
    body: ClarificationSubmissionRequest,
    request: Request,
    reviewer: Annotated[ReviewerIdentity, Depends(require_reviewer)],
    orchestrator: Annotated[WorkflowOrchestrator, Depends(get_orchestrator)],
) -> ClarificationSubmissionResponse:
    try:
        result = await orchestrator.submit_clarification(
            workflow_id,
            clarification_artifact_id=body.clarification_artifact_id,
            clarification_artifact_version=body.clarification_artifact_version,
            answers={item.question: item.answer for item in body.answers},
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
    return ClarificationSubmissionResponse.from_result(result)
