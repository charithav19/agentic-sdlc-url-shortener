# Phase 21 orchestration metrics assertions

- Counters reconstruct from committed workflow, stage, retry, compensation,
  policy, and approval records; no process-local counter is authoritative.
- `workflow_success_rate` uses `COMPLETED / (COMPLETED + FAILED)`.
- `stage_retry_frequency` uses scheduled retries / every started stage attempt.
- `workflow_rollback_frequency` uses distinct terminal workflows with a
  completed compensation / terminal workflows.
- MTTR begins at the first failure in an incident and ends at the next success
  for the same workflow generation and logical stage. Repeated failures do not
  reset the incident start.
- End-to-end latency begins at workflow creation and includes approval and
  clarification waits until the terminal transition.
- Prometheus output contains no high-cardinality workflow identifiers.
- The focused offline suite and HTTP contract test passed. The PostgreSQL test
  remains unexecuted because the sandbox denied Docker socket connections.
