# Phase 17 verification assertions

- Immutable artifact payloads are never updated or deleted during compensation.
- Candidate lifecycle metadata changes from `CANDIDATE` to `ROLLED_BACK` after a
  mandatory security validation failure.
- The prior exact approved artifact, approved lifecycle state, release approval,
  and approved candidate pointer remain available and become active again.
- The failed validation stage and workflow safe-stop only after compensation has
  restored the approved reference.
- `ROLLBACK_STARTED` precedes `ROLLBACK_COMPLETED`; both identify the candidate,
  failed validation cause, compensation record and restored artifact.
- Compensation is keyed by workflow, candidate and cause stage. Replaying the
  command returns the completed record and does not append duplicate rollback
  events.
- The rejected candidate payload and security failure evidence remain retained.

This evidence does not claim distributed database rollback, deployment rollback,
migration reversal, or filesystem snapshot restoration.
