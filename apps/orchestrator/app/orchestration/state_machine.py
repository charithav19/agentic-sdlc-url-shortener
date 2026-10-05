"""Explicit legal workflow and stage transition tables."""

from types import MappingProxyType

from app.orchestration.contracts import StageStatus, WorkflowStatus


class InvalidTransitionError(ValueError):
    pass


class StaleTransitionError(RuntimeError):
    pass


WORKFLOW_TRANSITIONS = MappingProxyType(
    {
        WorkflowStatus.CREATED: frozenset(
            {
                WorkflowStatus.RUNNING,
                WorkflowStatus.SAFE_STOPPED,
                WorkflowStatus.FAILED,
                WorkflowStatus.CANCELLED,
            }
        ),
        WorkflowStatus.RUNNING: frozenset(
            {
                WorkflowStatus.WAITING_FOR_CLARIFICATION,
                WorkflowStatus.WAITING_FOR_APPROVAL,
                WorkflowStatus.REPLANNING,
                WorkflowStatus.SAFE_STOPPED,
                WorkflowStatus.COMPLETED,
                WorkflowStatus.FAILED,
                WorkflowStatus.CANCELLED,
            }
        ),
        WorkflowStatus.WAITING_FOR_CLARIFICATION: frozenset(
            {
                WorkflowStatus.REPLANNING,
                WorkflowStatus.SAFE_STOPPED,
                WorkflowStatus.FAILED,
                WorkflowStatus.CANCELLED,
            }
        ),
        WorkflowStatus.WAITING_FOR_APPROVAL: frozenset(
            {
                WorkflowStatus.RUNNING,
                WorkflowStatus.REPLANNING,
                WorkflowStatus.SAFE_STOPPED,
                WorkflowStatus.FAILED,
                WorkflowStatus.CANCELLED,
            }
        ),
        WorkflowStatus.REPLANNING: frozenset(
            {
                WorkflowStatus.RUNNING,
                WorkflowStatus.WAITING_FOR_CLARIFICATION,
                WorkflowStatus.WAITING_FOR_APPROVAL,
                WorkflowStatus.SAFE_STOPPED,
                WorkflowStatus.FAILED,
                WorkflowStatus.CANCELLED,
            }
        ),
        WorkflowStatus.SAFE_STOPPED: frozenset(
            {
                WorkflowStatus.RUNNING,
                WorkflowStatus.REPLANNING,
                WorkflowStatus.FAILED,
                WorkflowStatus.CANCELLED,
            }
        ),
        WorkflowStatus.COMPLETED: frozenset(),
        WorkflowStatus.FAILED: frozenset(),
        WorkflowStatus.CANCELLED: frozenset(),
    }
)


STAGE_TRANSITIONS = MappingProxyType(
    {
        StageStatus.PENDING: frozenset(
            {
                StageStatus.BLOCKED,
                StageStatus.READY,
                StageStatus.SKIPPED,
                StageStatus.CANCELLED,
            }
        ),
        StageStatus.BLOCKED: frozenset(
            {
                StageStatus.READY,
                StageStatus.SKIPPED,
                StageStatus.SAFE_STOPPED,
                StageStatus.CANCELLED,
            }
        ),
        StageStatus.READY: frozenset(
            {
                StageStatus.BLOCKED,
                StageStatus.RUNNING,
                StageStatus.FALLBACK_RUNNING,
                StageStatus.SKIPPED,
                StageStatus.SAFE_STOPPED,
                StageStatus.CANCELLED,
            }
        ),
        StageStatus.RUNNING: frozenset(
            {
                StageStatus.WAITING_APPROVAL,
                StageStatus.SUCCEEDED,
                StageStatus.FAILED,
                StageStatus.SAFE_STOPPED,
                StageStatus.CANCELLED,
            }
        ),
        StageStatus.WAITING_APPROVAL: frozenset(
            {
                StageStatus.READY,
                StageStatus.SUCCEEDED,
                StageStatus.FAILED,
                StageStatus.SAFE_STOPPED,
                StageStatus.CANCELLED,
            }
        ),
        StageStatus.SUCCEEDED: frozenset({StageStatus.STALE, StageStatus.ROLLED_BACK}),
        StageStatus.FAILED: frozenset(
            {
                StageStatus.RETRY_PENDING,
                StageStatus.FALLBACK_RUNNING,
                StageStatus.ROLLED_BACK,
                StageStatus.SAFE_STOPPED,
                StageStatus.CANCELLED,
            }
        ),
        StageStatus.RETRY_PENDING: frozenset(
            {
                StageStatus.READY,
                StageStatus.FALLBACK_RUNNING,
                StageStatus.SAFE_STOPPED,
                StageStatus.CANCELLED,
            }
        ),
        StageStatus.FALLBACK_RUNNING: frozenset(
            {
                StageStatus.SUCCEEDED,
                StageStatus.FAILED,
                StageStatus.SAFE_STOPPED,
                StageStatus.CANCELLED,
            }
        ),
        StageStatus.ROLLED_BACK: frozenset(),
        StageStatus.STALE: frozenset(),
        StageStatus.SKIPPED: frozenset({StageStatus.STALE}),
        StageStatus.SAFE_STOPPED: frozenset(
            {StageStatus.READY, StageStatus.FAILED, StageStatus.CANCELLED}
        ),
        StageStatus.CANCELLED: frozenset(),
    }
)


def require_workflow_transition(
    current: WorkflowStatus,
    target: WorkflowStatus,
    *,
    completion_verified: bool = False,
) -> None:
    if target not in WORKFLOW_TRANSITIONS[current]:
        raise InvalidTransitionError(f"Illegal workflow transition: {current} -> {target}")
    if target == WorkflowStatus.COMPLETED and not completion_verified:
        raise InvalidTransitionError("Workflow completion requires verified release gates")


def require_stage_transition(current: StageStatus, target: StageStatus) -> None:
    if target not in STAGE_TRANSITIONS[current]:
        raise InvalidTransitionError(f"Illegal stage transition: {current} -> {target}")
