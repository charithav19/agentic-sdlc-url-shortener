# Phase 19 selective replanning verification assertions

- `POST /api/v1/workflows/{workflowId}/requirements` requires an authenticated
  human identity and accepts optimistic workflow version and update identity.
- Requirement V1 remains immutable. V2 receives the next logical version and an
  exact `SUPERSEDES` edge from V1.
- Repeating the same update identity and content is idempotent, including when
  the supplied expected version is now old.
- The prior requirement's transitive lineage closure determines stale artifacts;
  configured DAG dependencies determine the new affected stage closure.
- Architecture, implementation, expiry-test and API-documentation artifacts are
  stale, inactive, and retained for inspection.
- Pending or approved decisions on stale artifacts become `INVALIDATED`; no
  approval is transferred to a new artifact version.
- Independent analytics content has no affected lineage edge, so its approved,
  active lifecycle and succeeded stage remain unchanged.
- Old affected stage attempts become `STALE`. The workflow increments to a new
  generation with human requirement analysis recorded as succeeded,
  `TASK_DECOMPOSITION` ready, and architecture design/approval blocked.
- `REPLAN_STARTED` precedes `REPLAN_COMPLETED`; the audit payload records the
  update identity, exact requirement versions, affected artifacts/stages, and
  invalidated approvals.

This evidence does not claim that revised planning/design specialists have
already run, that a new architecture has been approved, or that aggregate
validation and release approval have completed.
