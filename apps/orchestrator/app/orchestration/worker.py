"""Claim-fenced stage worker used by the bounded asyncio scheduler."""

import uuid
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from app.orchestration.claims import ClaimUnavailableError, StageClaim, StaleClaimError
from app.orchestration.commands import TransitionContext
from app.orchestration.failure_classifier import (
    FailureClassification,
    FailureClassifier,
    InvalidWorkflowStateFailure,
)
from app.orchestration.orchestrator import WorkflowOrchestrator

StageExecutor = Callable[[StageClaim], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class StageWorkResult:
    stage_run_id: uuid.UUID
    stage_name: str | None
    claimed: bool
    committed: bool
    succeeded: bool | None
    error: str | None = None
    failure: FailureClassification | None = None


class StageWorker:
    def __init__(
        self,
        orchestrator: WorkflowOrchestrator,
        executors: Mapping[str, StageExecutor],
        *,
        owner: str,
        lease_seconds: int,
        failure_classifier: FailureClassifier | None = None,
    ) -> None:
        self.orchestrator = orchestrator
        self.executors = dict(executors)
        self.owner = owner
        self.lease_seconds = lease_seconds
        self.failure_classifier = failure_classifier or FailureClassifier()

    async def run(self, stage_run_id: uuid.UUID) -> StageWorkResult:
        trace_id = uuid.uuid4()
        context = TransitionContext(
            actor_type="SYSTEM",
            actor_id=self.owner,
            trace_id=trace_id,
        )
        try:
            claim = await self.orchestrator.claim_stage(
                stage_run_id,
                owner=self.owner,
                lease_seconds=self.lease_seconds,
                context=context,
            )
        except ClaimUnavailableError as error:
            return StageWorkResult(
                stage_run_id=stage_run_id,
                stage_name=None,
                claimed=False,
                committed=False,
                succeeded=None,
                error=str(error),
            )

        executor = self.executors.get(claim.executor)
        succeeded = True
        error_message: str | None = None
        payload: dict[str, Any] | None = None
        failure: FailureClassification | None = None
        if executor is None:
            succeeded = False
            error = InvalidWorkflowStateFailure(
                f"No stage executor registered for {claim.executor}"
            )
            failure = self.failure_classifier.classify(error)
            error_message = f"{type(error).__name__}: {error}"[:2000]
        else:
            try:
                payload = await executor(claim)
            except Exception as error:  # noqa: BLE001 - executor failure becomes stage evidence
                succeeded = False
                failure = self.failure_classifier.classify(error)
                error_message = f"{type(error).__name__}: {error}"[:2000]

        try:
            await self.orchestrator.complete_stage_claim(
                claim,
                succeeded=succeeded,
                result=payload,
                error_message=error_message,
                failure_code=failure.code.value if failure else None,
                recommended_action=failure.recommended_human_action if failure else None,
                context=context,
            )
        except StaleClaimError as error:
            return StageWorkResult(
                stage_run_id=stage_run_id,
                stage_name=claim.stage_name,
                claimed=True,
                committed=False,
                succeeded=None,
                error=str(error),
            )
        return StageWorkResult(
            stage_run_id=stage_run_id,
            stage_name=claim.stage_name,
            claimed=True,
            committed=True,
            succeeded=succeeded,
            error=error_message,
            failure=failure,
        )
