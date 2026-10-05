"""Read restart-stable orchestration metrics from durable PostgreSQL state."""

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.observability.metrics import (
    ReliabilityMetrics,
    StageOutcome,
    StageTiming,
    WorkflowTiming,
    calculate_metrics,
)
from app.persistence.models import (
    Approval,
    AuditEvent,
    Compensation,
    PolicyEvent,
    StageRun,
    WorkflowRun,
)


class MetricsReporter:
    """Build an all-time snapshot from committed records only."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def snapshot(self) -> ReliabilityMetrics:
        workflow_rows = list(
            await self.session.execute(
                select(WorkflowRun.id, WorkflowRun._status, WorkflowRun.created_at)
            )
        )
        event_rows = list(
            await self.session.execute(
                select(
                    AuditEvent.workflow_id,
                    AuditEvent.stage_run_id,
                    AuditEvent.sequence,
                    AuditEvent.occurred_at,
                    AuditEvent.event_type,
                    AuditEvent.before_state,
                    AuditEvent.after_state,
                    AuditEvent.payload,
                ).where(
                    (AuditEvent.event_type == "WORKFLOW_STATUS_CHANGED")
                    | (AuditEvent.event_type == "STAGE_RETRY_SCHEDULED")
                    | (AuditEvent.after_state.in_(("SUCCEEDED", "FAILED", "SAFE_STOPPED")))
                )
            )
        )

        stage_rows = list(
            await self.session.execute(
                select(
                    StageRun.id,
                    StageRun.stage_name,
                    StageRun.generation,
                    StageRun.started_at,
                    StageRun.completed_at,
                ).where(StageRun.started_at.is_not(None))
            )
        )
        stage_identity = {row.id: (row.stage_name, row.generation) for row in stage_rows}

        workflow_events: dict[object, list] = defaultdict(list)
        stage_outcomes: list[StageOutcome] = []
        safe_stop_entries = 0
        retry_attempts = 0
        for event in event_rows:
            if event.event_type == "WORKFLOW_STATUS_CHANGED":
                workflow_events[event.workflow_id].append(event)
                if event.after_state == "SAFE_STOPPED":
                    safe_stop_entries += 1
            if event.event_type == "STAGE_RETRY_SCHEDULED":
                retry_attempts += 1
            if event.stage_run_id is not None and event.after_state in {
                "SUCCEEDED",
                "FAILED",
                "SAFE_STOPPED",
            }:
                stage_name = event.payload.get("stage_name")
                generation = event.payload.get("generation")
                if (not isinstance(stage_name, str) or not isinstance(generation, int)) and (
                    event.stage_run_id in stage_identity
                ):
                    stage_name, generation = stage_identity[event.stage_run_id]
                if isinstance(stage_name, str) and isinstance(generation, int):
                    stage_outcomes.append(
                        StageOutcome(
                            workflow_id=event.workflow_id,
                            generation=generation,
                            stage_name=stage_name,
                            sequence=event.sequence,
                            occurred_at=event.occurred_at,
                            outcome=event.after_state,
                        )
                    )

        workflows: list[WorkflowTiming] = []
        for workflow_id, status, created_at in workflow_rows:
            events = workflow_events[workflow_id]
            started_at = min(
                (event.occurred_at for event in events if event.after_state == "RUNNING"),
                default=None,
            )
            terminal_at = min(
                (
                    event.occurred_at
                    for event in events
                    if event.after_state in {"COMPLETED", "FAILED"}
                ),
                default=None,
            )
            workflows.append(
                WorkflowTiming(
                    workflow_id=workflow_id,
                    status=status.value,
                    created_at=created_at,
                    started_at=started_at,
                    terminal_at=terminal_at,
                )
            )

        stages = [
            StageTiming(started_at=row.started_at, completed_at=row.completed_at)
            for row in stage_rows
        ]

        completed_compensations = list(
            await self.session.scalars(
                select(Compensation.workflow_id).where(Compensation.status == "COMPLETED")
            )
        )
        policy_violations = len(
            list(
                await self.session.scalars(
                    select(PolicyEvent.id).where(PolicyEvent.result == "DENY")
                )
            )
        )
        approvals = list(await self.session.scalars(select(Approval.status)))
        return calculate_metrics(
            workflows=workflows,
            stages=stages,
            stage_outcomes=stage_outcomes,
            safe_stop_entries=safe_stop_entries,
            retry_attempts=retry_attempts,
            rollback_count=len(completed_compensations),
            rollback_workflow_ids=set(completed_compensations),
            policy_violations=policy_violations,
            approval_wait_entries=len(approvals),
            pending_approvals=sum(status == "PENDING" for status in approvals),
        )
