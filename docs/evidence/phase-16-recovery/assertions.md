# Phase 16 verification assertions

- `RetryPolicy` defaults to two total primary attempts. The classifier retries
  only OpenAI timeout, temporary external-provider error, and temporary
  workspace-tool failure.
- Retry timing uses bounded exponential delay and deterministic bounded jitter.
  A retry receives a new `stage_runs` identity; the failed row and its exact
  error classification remain unchanged.
- A configured fallback is scheduled only after transient primary exhaustion.
  It has a separate row, `FALLBACK` execution mode, `FALLBACK_RUNNING` claim
  transition, executor, and source-stage reference.
- Policy violations, failed assertions, invalid requirements, security
  violations, forbidden tools, invalid workflow state, and corrupted lineage do
  not auto-retry.
- Safe-stop stores the failure reason and recommended human action, retains the
  last successful stage, and atomically moves the failing stage and workflow to
  `SAFE_STOPPED`. A stopped workflow returns no ready claims, so descendants do
  not execute.
- Human recovery requires reviewer authentication at the API boundary, an
  explicit resolved-cause assertion, optimistic workflow version, the exact
  latest stopped attempt, and current exact artifact inputs. It preserves the
  stopped row and creates a new pending attempt.
- Retry, fallback, safe-stop and recovery decisions append causal audit events.

These assertions do not claim a continuously running scheduler daemon,
automatic lease/uncertain-side-effect reconciliation, Phase 21 metrics, live
OpenAI outage evidence, or full runtime stage-gate evaluation.
