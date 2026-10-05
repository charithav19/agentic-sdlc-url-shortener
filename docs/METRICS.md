# Orchestrator metrics

The FastAPI orchestrator exposes Prometheus 0.0.4 text at `GET /metrics`. The
snapshot is rebuilt from committed PostgreSQL workflow, stage, approval,
compensation, policy, and audit records. Process restarts therefore do not reset
or double-count the values.

The current reporting cohort is all retained data. Metrics carry no workflow,
stage, actor, trace, or artifact labels; use the audit records for per-workflow
diagnosis. A future bounded-window reporting API may reuse the same calculator.

## Counters and histograms

| Metric | Definition |
|---|---|
| `workflow_started_total` | Workflows with a committed transition into `RUNNING` |
| `workflow_completed_total` | Workflows whose terminal status is `COMPLETED` |
| `workflow_failed_total` | Workflows whose terminal status is `FAILED` |
| `workflow_safe_stopped_total` | Committed entries into recoverable `SAFE_STOPPED`; repeat incidents count separately |
| `stage_execution_total` | Stage attempts with `started_at`, including attempts still running |
| `stage_retry_total` | Committed `STAGE_RETRY_SCHEDULED` events |
| `stage_rollback_total` | Completed compensation records |
| `workflow_duration_seconds` | Histogram of first `RUNNING` transition to `COMPLETED` or `FAILED` |
| `stage_duration_seconds` | Histogram of `completed_at - started_at` for completed attempts |
| `policy_violation_total` | Durable policy decisions with result `DENY` |
| `approval_waiting_total` | Approval checkpoints created; this counter is not the current queue size |

`approval_waiting_current` separately reports the current number of `PENDING`
approvals.

## Reliability calculations

Terminal workflows are `COMPLETED` plus `FAILED`. `CANCELLED` and unresolved
`SAFE_STOPPED` workflows are reported separately and do not bias the success
rate.

- `workflow_success_rate = completed / (completed + failed)`
- `stage_retry_frequency = retry attempts / stage executions`
- `workflow_rollback_frequency = terminal workflows with at least one completed compensation / terminal workflows`
- `workflow_mttr_seconds` is a histogram of the next successful attempt time
  minus the first failure time for each workflow generation and logical stage.
  Consecutive failures belong to one incident; `workflow_recovery_unresolved`
  reports incidents without a later success.
- `workflow_end_to_end_latency_seconds` is a histogram of terminal transition
  time minus workflow `created_at`, including approval and clarification waits.

A ratio with a zero denominator is exported as Prometheus `NaN`. Histograms
remain valid with `_count 0`. Negative elapsed values caused by malformed or
legacy timestamps are clamped to zero.

The endpoint currently performs an all-time reporting query. Reporting indexes
cover state, event time, approval state, stage timestamps, and compensation
completion. Long-retention deployments should add recording rules or bounded
window materialization before the retained tables become large.
