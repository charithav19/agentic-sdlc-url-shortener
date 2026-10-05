"""Deterministic reliability metric definitions and Prometheus rendering."""

import math
import uuid
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime

TERMINAL_STATUSES = frozenset({"COMPLETED", "FAILED"})
FAILURE_OUTCOMES = frozenset({"FAILED", "SAFE_STOPPED"})
HISTOGRAM_BUCKETS = (0.1, 0.5, 1.0, 5.0, 15.0, 60.0, 300.0, 900.0, 3600.0)


@dataclass(frozen=True)
class WorkflowTiming:
    workflow_id: uuid.UUID
    status: str
    created_at: datetime
    started_at: datetime | None = None
    terminal_at: datetime | None = None


@dataclass(frozen=True)
class StageTiming:
    started_at: datetime
    completed_at: datetime | None = None


@dataclass(frozen=True)
class StageOutcome:
    workflow_id: uuid.UUID
    generation: int
    stage_name: str
    sequence: int
    occurred_at: datetime
    outcome: str


@dataclass(frozen=True)
class ReliabilityMetrics:
    workflow_started_total: int
    workflow_completed_total: int
    workflow_failed_total: int
    workflow_safe_stopped_total: int
    stage_execution_total: int
    stage_retry_total: int
    stage_rollback_total: int
    policy_violation_total: int
    approval_waiting_total: int
    approval_waiting_current: int
    terminal_workflow_total: int
    workflows_with_rollback_total: int
    unresolved_recovery_total: int
    workflow_success_rate: float | None
    stage_retry_frequency: float | None
    workflow_rollback_frequency: float | None
    workflow_durations: tuple[float, ...]
    stage_durations: tuple[float, ...]
    mttr_durations: tuple[float, ...]
    end_to_end_latencies: tuple[float, ...]


def calculate_metrics(
    *,
    workflows: Sequence[WorkflowTiming],
    stages: Sequence[StageTiming],
    stage_outcomes: Sequence[StageOutcome],
    safe_stop_entries: int,
    retry_attempts: int,
    rollback_count: int,
    rollback_workflow_ids: set[uuid.UUID],
    policy_violations: int,
    approval_wait_entries: int,
    pending_approvals: int,
) -> ReliabilityMetrics:
    """Calculate documented all-time metrics from durable records."""

    completed = sum(item.status == "COMPLETED" for item in workflows)
    failed = sum(item.status == "FAILED" for item in workflows)
    terminal_ids = {item.workflow_id for item in workflows if item.status in TERMINAL_STATUSES}
    terminal_total = completed + failed
    executions = len(stages)
    workflows_with_rollback = len(terminal_ids & rollback_workflow_ids)

    workflow_durations = tuple(
        _elapsed(item.started_at, item.terminal_at)
        for item in workflows
        if item.status in TERMINAL_STATUSES
        and item.started_at is not None
        and item.terminal_at is not None
    )
    end_to_end = tuple(
        _elapsed(item.created_at, item.terminal_at)
        for item in workflows
        if item.status in TERMINAL_STATUSES and item.terminal_at is not None
    )
    stage_durations = tuple(
        _elapsed(item.started_at, item.completed_at)
        for item in stages
        if item.completed_at is not None
    )
    mttr, unresolved = _calculate_mttr(stage_outcomes)

    return ReliabilityMetrics(
        workflow_started_total=sum(item.started_at is not None for item in workflows),
        workflow_completed_total=completed,
        workflow_failed_total=failed,
        workflow_safe_stopped_total=safe_stop_entries,
        stage_execution_total=executions,
        stage_retry_total=retry_attempts,
        stage_rollback_total=rollback_count,
        policy_violation_total=policy_violations,
        approval_waiting_total=approval_wait_entries,
        approval_waiting_current=pending_approvals,
        terminal_workflow_total=terminal_total,
        workflows_with_rollback_total=workflows_with_rollback,
        unresolved_recovery_total=unresolved,
        workflow_success_rate=_ratio(completed, terminal_total),
        stage_retry_frequency=_ratio(retry_attempts, executions),
        workflow_rollback_frequency=_ratio(workflows_with_rollback, terminal_total),
        workflow_durations=workflow_durations,
        stage_durations=stage_durations,
        mttr_durations=mttr,
        end_to_end_latencies=end_to_end,
    )


def render_prometheus(metrics: ReliabilityMetrics) -> str:
    """Render Prometheus 0.0.4 text without workflow or stage labels."""

    lines: list[str] = []
    counters = (
        (
            "workflow_started_total",
            "Workflows that entered RUNNING.",
            metrics.workflow_started_total,
        ),
        ("workflow_completed_total", "Workflows in COMPLETED.", metrics.workflow_completed_total),
        ("workflow_failed_total", "Workflows in FAILED.", metrics.workflow_failed_total),
        (
            "workflow_safe_stopped_total",
            "Entries into the recoverable SAFE_STOPPED state.",
            metrics.workflow_safe_stopped_total,
        ),
        (
            "stage_execution_total",
            "Stage attempts that started execution.",
            metrics.stage_execution_total,
        ),
        ("stage_retry_total", "Retry attempts scheduled.", metrics.stage_retry_total),
        (
            "stage_rollback_total",
            "Completed stage-triggered compensations.",
            metrics.stage_rollback_total,
        ),
        ("policy_violation_total", "Denied policy evaluations.", metrics.policy_violation_total),
        (
            "approval_waiting_total",
            "Approval wait entries created; this is not the current queue size.",
            metrics.approval_waiting_total,
        ),
    )
    for name, help_text, value in counters:
        _append_scalar(lines, name, help_text, "counter", value)

    gauges = (
        (
            "approval_waiting_current",
            "Approvals currently pending.",
            metrics.approval_waiting_current,
        ),
        (
            "workflow_terminal_total",
            "Terminal workflows used by reliability ratios (COMPLETED plus FAILED).",
            metrics.terminal_workflow_total,
        ),
        (
            "workflow_with_rollback_total",
            "Terminal workflows with at least one completed rollback.",
            metrics.workflows_with_rollback_total,
        ),
        (
            "workflow_recovery_unresolved",
            "Stage failure incidents without a later successful attempt.",
            metrics.unresolved_recovery_total,
        ),
        (
            "workflow_success_rate",
            "Completed workflows divided by COMPLETED plus FAILED workflows.",
            metrics.workflow_success_rate,
        ),
        (
            "stage_retry_frequency",
            "Retry attempts divided by stage executions.",
            metrics.stage_retry_frequency,
        ),
        (
            "workflow_rollback_frequency",
            "Terminal workflows with rollback divided by terminal workflows.",
            metrics.workflow_rollback_frequency,
        ),
    )
    for name, help_text, value in gauges:
        _append_scalar(lines, name, help_text, "gauge", value)

    _append_histogram(
        lines,
        "workflow_duration_seconds",
        "Time from first RUNNING transition to terminal transition.",
        metrics.workflow_durations,
    )
    _append_histogram(
        lines,
        "stage_duration_seconds",
        "Time from stage execution start to completion.",
        metrics.stage_durations,
    )
    _append_histogram(
        lines,
        "workflow_mttr_seconds",
        "Time from first stage failure to its next successful logical-stage attempt.",
        metrics.mttr_durations,
    )
    _append_histogram(
        lines,
        "workflow_end_to_end_latency_seconds",
        "Time from workflow creation to terminal transition, including waits.",
        metrics.end_to_end_latencies,
    )
    return "\n".join(lines) + "\n"


def _calculate_mttr(outcomes: Sequence[StageOutcome]) -> tuple[tuple[float, ...], int]:
    grouped: dict[tuple[uuid.UUID, int, str], list[StageOutcome]] = defaultdict(list)
    for outcome in outcomes:
        grouped[(outcome.workflow_id, outcome.generation, outcome.stage_name)].append(outcome)

    durations: list[float] = []
    unresolved = 0
    for events in grouped.values():
        first_failure_at: datetime | None = None
        for event in sorted(events, key=lambda item: (item.occurred_at, item.sequence)):
            if event.outcome in FAILURE_OUTCOMES:
                first_failure_at = first_failure_at or event.occurred_at
            elif event.outcome == "SUCCEEDED" and first_failure_at is not None:
                durations.append(_elapsed(first_failure_at, event.occurred_at))
                first_failure_at = None
        unresolved += first_failure_at is not None
    return tuple(durations), unresolved


def _elapsed(start: datetime, end: datetime) -> float:
    return max(0.0, (end - start).total_seconds())


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _append_scalar(
    lines: list[str], name: str, help_text: str, metric_type: str, value: int | float | None
) -> None:
    rendered = (
        "NaN" if value is None or (isinstance(value, float) and math.isnan(value)) else str(value)
    )
    lines.extend(
        (f"# HELP {name} {help_text}", f"# TYPE {name} {metric_type}", f"{name} {rendered}")
    )


def _append_histogram(lines: list[str], name: str, help_text: str, values: Iterable[float]) -> None:
    observations = tuple(values)
    lines.extend((f"# HELP {name} {help_text}", f"# TYPE {name} histogram"))
    for bucket in HISTOGRAM_BUCKETS:
        count = sum(value <= bucket for value in observations)
        lines.append(f'{name}_bucket{{le="{bucket:g}"}} {count}')
    lines.append(f'{name}_bucket{{le="+Inf"}} {len(observations)}')
    lines.append(f"{name}_sum {sum(observations):g}")
    lines.append(f"{name}_count {len(observations)}")
