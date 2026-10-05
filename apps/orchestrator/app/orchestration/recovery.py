"""Policy coordinator for retry, fallback, and durable safe-stop."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.orchestration.commands import TransitionContext
from app.orchestration.compensation import CompensationCoordinator
from app.orchestration.contracts import WorkflowStatus
from app.orchestration.failure_classifier import FailureClassification
from app.orchestration.fallback import fallback_after_exhaustion
from app.orchestration.graph import WorkflowGraph
from app.orchestration.orchestrator import WorkflowOrchestrator
from app.orchestration.retries import RetryPlanner
from app.persistence.models import StageRun, WorkflowRun
from app.persistence.session import session_scope


class RecoveryAction(StrEnum):
    RETRY_SCHEDULED = "RETRY_SCHEDULED"
    FALLBACK_SCHEDULED = "FALLBACK_SCHEDULED"
    SAFE_STOPPED = "SAFE_STOPPED"


@dataclass(frozen=True)
class RecoveryResult:
    failed_stage_run_id: uuid.UUID
    action: RecoveryAction
    next_stage_run_id: uuid.UUID | None = None
    compensation_id: uuid.UUID | None = None


class RecoveryCoordinator:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        graph: WorkflowGraph,
        orchestrator: WorkflowOrchestrator,
        *,
        retry_planner: RetryPlanner | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.graph = graph
        self.orchestrator = orchestrator
        self.retry_planner = retry_planner or RetryPlanner()
        self.compensation = CompensationCoordinator(session_factory)

    async def recover(
        self,
        stage_run_id: uuid.UUID,
        *,
        failure: FailureClassification,
        failure_reason: str,
        actor_id: str,
        trace_id: uuid.UUID,
    ) -> RecoveryResult:
        async with session_scope(self.session_factory) as session:
            stage = await session.get(StageRun, stage_run_id)
            if stage is None:
                raise KeyError(f"Unknown stage run {stage_run_id}")
            workflow = await session.get(WorkflowRun, stage.workflow_id)
            if workflow is None:
                raise KeyError(f"Unknown workflow {stage.workflow_id}")
            definition = self.graph.stage(stage.stage_name)
            attempt = stage.attempt
            execution_mode = stage.execution_mode
            workflow_running = workflow.status is WorkflowStatus.RUNNING

        context = TransitionContext(
            actor_type="SYSTEM",
            actor_id=actor_id,
            trace_id=trace_id,
            reason=failure_reason,
        )
        compensation_id: uuid.UUID | None = None
        if not failure.retryable:
            try:
                compensated = await self.compensation.compensate_active_candidate_for_stage(
                    stage_run_id,
                    failure_reason=failure_reason,
                    context=context,
                )
                compensation_id = compensated.compensation_id if compensated else None
            except Exception as error:  # noqa: BLE001 - compensation failure must safe-stop
                failure_reason = (
                    f"{failure_reason}; compensation failed: {type(error).__name__}: {error}"
                )[:2000]
        if not workflow_running:
            await self.orchestrator.safe_stop(
                stage_run_id,
                failure_reason=failure_reason,
                failure_code=failure.code.value,
                recommended_action=failure.recommended_human_action,
                context=context,
            )
            return RecoveryResult(
                stage_run_id,
                RecoveryAction.SAFE_STOPPED,
                compensation_id=compensation_id,
            )
        if (
            failure.retryable
            and execution_mode == "PRIMARY"
            and (attempt < definition.retry_policy.max_attempts)
        ):
            jitter = (stage_run_id.int % 1000) / 1000
            schedule = self.retry_planner.schedule(
                completed_attempt=attempt,
                now=datetime.now(UTC),
                jitter_fraction=jitter,
            )
            next_id = await self.orchestrator.schedule_retry(
                stage_run_id,
                due_at=schedule.due_at,
                context=context,
            )
            return RecoveryResult(stage_run_id, RecoveryAction.RETRY_SCHEDULED, next_id)

        fallback = (
            fallback_after_exhaustion(
                definition,
                source_attempt=attempt,
                execution_mode=execution_mode,
            )
            if failure.retryable
            else None
        )
        if fallback is not None:
            next_id = await self.orchestrator.schedule_fallback(
                stage_run_id,
                fallback_executor=fallback.executor,
                context=context,
            )
            return RecoveryResult(stage_run_id, RecoveryAction.FALLBACK_SCHEDULED, next_id)

        await self.orchestrator.safe_stop(
            stage_run_id,
            failure_reason=failure_reason,
            failure_code=failure.code.value,
            recommended_action=failure.recommended_human_action,
            context=context,
        )
        return RecoveryResult(
            stage_run_id,
            RecoveryAction.SAFE_STOPPED,
            compensation_id=compensation_id,
        )
