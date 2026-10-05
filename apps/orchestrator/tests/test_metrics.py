"""Orchestration reliability calculations and Prometheus endpoint."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.dependencies import get_session
from app.main import app
from app.observability.metrics import (
    ReliabilityMetrics,
    StageOutcome,
    StageTiming,
    WorkflowTiming,
    calculate_metrics,
    render_prometheus,
)
from app.observability.reporting import MetricsReporter
from app.orchestration.contracts import ScenarioType, StageStatus, WorkflowStatus
from app.persistence.models import AuditEvent, StageRun, WorkflowRun
from app.persistence.session import session_scope


def test_required_metrics_and_ratios_use_documented_denominators() -> None:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    completed_id = uuid.uuid4()
    failed_id = uuid.uuid4()
    running_id = uuid.uuid4()
    metrics = calculate_metrics(
        workflows=(
            WorkflowTiming(
                completed_id,
                "COMPLETED",
                base,
                base + timedelta(seconds=10),
                base + timedelta(seconds=100),
            ),
            WorkflowTiming(
                failed_id,
                "FAILED",
                base,
                base + timedelta(seconds=20),
                base + timedelta(seconds=200),
            ),
            WorkflowTiming(running_id, "RUNNING", base, base + timedelta(seconds=5)),
        ),
        stages=(
            StageTiming(base, base + timedelta(seconds=10)),
            StageTiming(base, base + timedelta(seconds=20)),
            StageTiming(base, base + timedelta(seconds=30)),
            StageTiming(base, base + timedelta(seconds=40)),
            StageTiming(base),
        ),
        stage_outcomes=(
            StageOutcome(completed_id, 1, "BUILD", 1, base + timedelta(seconds=30), "FAILED"),
            StageOutcome(completed_id, 1, "BUILD", 2, base + timedelta(seconds=40), "FAILED"),
            StageOutcome(completed_id, 1, "BUILD", 3, base + timedelta(seconds=70), "SUCCEEDED"),
            StageOutcome(failed_id, 1, "SECURITY", 1, base, "SAFE_STOPPED"),
        ),
        safe_stop_entries=2,
        retry_attempts=2,
        rollback_count=2,
        rollback_workflow_ids={completed_id, running_id},
        policy_violations=3,
        approval_wait_entries=4,
        pending_approvals=1,
    )

    assert metrics.workflow_started_total == 3
    assert metrics.workflow_completed_total == 1
    assert metrics.workflow_failed_total == 1
    assert metrics.workflow_safe_stopped_total == 2
    assert metrics.stage_execution_total == 5
    assert metrics.stage_retry_total == 2
    assert metrics.stage_rollback_total == 2
    assert metrics.policy_violation_total == 3
    assert metrics.approval_waiting_total == 4
    assert metrics.workflow_success_rate == 0.5
    assert metrics.stage_retry_frequency == 0.4
    assert metrics.workflow_rollback_frequency == 0.5
    assert metrics.workflow_durations == (90.0, 180.0)
    assert metrics.end_to_end_latencies == (100.0, 200.0)
    assert metrics.mttr_durations == (40.0,)
    assert metrics.unresolved_recovery_total == 1


def test_zero_denominators_render_as_nan_and_histograms_are_empty() -> None:
    metrics = calculate_metrics(
        workflows=(),
        stages=(),
        stage_outcomes=(),
        safe_stop_entries=0,
        retry_attempts=0,
        rollback_count=0,
        rollback_workflow_ids=set(),
        policy_violations=0,
        approval_wait_entries=0,
        pending_approvals=0,
    )

    output = render_prometheus(metrics)

    assert "workflow_success_rate NaN" in output
    assert "stage_retry_frequency NaN" in output
    assert "workflow_rollback_frequency NaN" in output
    assert "workflow_duration_seconds_count 0" in output
    assert "stage_duration_seconds_count 0" in output
    assert "workflow_mttr_seconds_count 0" in output
    assert "workflow_end_to_end_latency_seconds_count 0" in output


def test_prometheus_output_contains_every_required_metric() -> None:
    metrics = ReliabilityMetrics(
        workflow_started_total=1,
        workflow_completed_total=1,
        workflow_failed_total=0,
        workflow_safe_stopped_total=0,
        stage_execution_total=2,
        stage_retry_total=1,
        stage_rollback_total=1,
        policy_violation_total=1,
        approval_waiting_total=1,
        approval_waiting_current=0,
        terminal_workflow_total=1,
        workflows_with_rollback_total=1,
        unresolved_recovery_total=0,
        workflow_success_rate=1.0,
        stage_retry_frequency=0.5,
        workflow_rollback_frequency=1.0,
        workflow_durations=(12.0,),
        stage_durations=(5.0, 7.0),
        mttr_durations=(3.0,),
        end_to_end_latencies=(15.0,),
    )

    output = render_prometheus(metrics)

    for required in (
        "workflow_started_total",
        "workflow_completed_total",
        "workflow_failed_total",
        "workflow_safe_stopped_total",
        "stage_execution_total",
        "stage_retry_total",
        "stage_rollback_total",
        "workflow_duration_seconds",
        "stage_duration_seconds",
        "policy_violation_total",
        "approval_waiting_total",
        "workflow_success_rate",
        "stage_retry_frequency",
        "workflow_rollback_frequency",
        "workflow_mttr_seconds",
        "workflow_end_to_end_latency_seconds",
    ):
        assert f"# TYPE {required} " in output


@pytest.mark.asyncio
async def test_metrics_endpoint_exposes_prometheus_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    empty = calculate_metrics(
        workflows=(),
        stages=(),
        stage_outcomes=(),
        safe_stop_entries=0,
        retry_attempts=0,
        rollback_count=0,
        rollback_workflow_ids=set(),
        policy_violations=0,
        approval_wait_entries=0,
        pending_approvals=0,
    )

    async def snapshot(_reporter):
        return empty

    monkeypatch.setattr(MetricsReporter, "snapshot", snapshot)
    app.dependency_overrides[get_session] = lambda: object()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://orchestrator.test"
        ) as client:
            response = await client.get("/metrics")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain; version=0.0.4")
    assert "workflow_started_total 0" in response.text
    assert "workflow_success_rate NaN" in response.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_metrics_endpoint_reads_committed_workflow_and_stage_events(
    phase6_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_scope(phase6_factory) as session:
        baseline = await MetricsReporter(session).snapshot()
    base = datetime(2026, 1, 1, tzinfo=UTC)
    workflow_id = uuid.uuid4()
    workflow = WorkflowRun(
        id=workflow_id,
        scenario_type=ScenarioType.GREENFIELD,
        _status=WorkflowStatus.COMPLETED,
        provider_mode="fake",
        workspace_ref="workspaces/metrics",
        created_at=base,
    )
    stage = StageRun(
        workflow_id=workflow_id,
        stage_name="BUILD_VALIDATION",
        generation=1,
        attempt=1,
        _status=StageStatus.SUCCEEDED,
        executor="fake",
        started_at=base + timedelta(seconds=10),
        completed_at=base + timedelta(seconds=30),
    )
    async with session_scope(phase6_factory) as session:
        session.add(workflow)
        await session.flush()
        session.add(stage)
        await session.flush()
        session.add_all(
            (
                AuditEvent(
                    workflow_id=workflow.id,
                    sequence=1,
                    occurred_at=base + timedelta(seconds=5),
                    actor_type="SYSTEM",
                    actor_id="orchestrator",
                    event_type="WORKFLOW_STATUS_CHANGED",
                    before_state="CREATED",
                    after_state="RUNNING",
                ),
                AuditEvent(
                    workflow_id=workflow.id,
                    stage_run_id=stage.id,
                    sequence=2,
                    occurred_at=base + timedelta(seconds=15),
                    actor_type="SYSTEM",
                    actor_id="orchestrator",
                    event_type="STAGE_CLAIM_FAILED",
                    before_state="RUNNING",
                    after_state="FAILED",
                    payload={"stage_name": stage.stage_name, "generation": 1},
                ),
                AuditEvent(
                    workflow_id=workflow.id,
                    stage_run_id=stage.id,
                    sequence=3,
                    occurred_at=base + timedelta(seconds=30),
                    actor_type="SYSTEM",
                    actor_id="orchestrator",
                    event_type="STAGE_CLAIM_COMPLETED",
                    before_state="RUNNING",
                    after_state="SUCCEEDED",
                    payload={"stage_name": stage.stage_name, "generation": 1},
                ),
                AuditEvent(
                    workflow_id=workflow.id,
                    sequence=4,
                    occurred_at=base + timedelta(seconds=40),
                    actor_type="SYSTEM",
                    actor_id="orchestrator",
                    event_type="WORKFLOW_STATUS_CHANGED",
                    before_state="RUNNING",
                    after_state="COMPLETED",
                ),
            )
        )

    async def override_session():
        async with session_scope(phase6_factory) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://orchestrator.test"
        ) as client:
            response = await client.get("/metrics")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain; version=0.0.4")

    def metric(name: str) -> float:
        prefix = f"{name} "
        return float(
            next(
                line.removeprefix(prefix)
                for line in response.text.splitlines()
                if line.startswith(prefix)
            )
        )

    assert metric("workflow_started_total") == baseline.workflow_started_total + 1
    assert metric("workflow_completed_total") == baseline.workflow_completed_total + 1
    assert metric("stage_execution_total") == baseline.stage_execution_total + 1
    assert metric("workflow_duration_seconds_sum") == pytest.approx(
        sum(baseline.workflow_durations) + 35, abs=1e-3
    )
    assert metric("workflow_end_to_end_latency_seconds_sum") == pytest.approx(
        sum(baseline.end_to_end_latencies) + 40, abs=1e-3
    )
    assert metric("workflow_mttr_seconds_sum") == pytest.approx(
        sum(baseline.mttr_durations) + 15, abs=1e-3
    )
