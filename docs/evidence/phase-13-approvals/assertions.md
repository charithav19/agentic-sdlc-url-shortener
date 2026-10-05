# Phase 13 approval verification assertions

- Approval types are exactly `ARCHITECTURE`, `HIGH_IMPACT_CHANGE`, `ASSUMPTION`,
  and `RELEASE`; statuses are exactly `PENDING`, `APPROVED`, `REJECTED`, and
  `INVALIDATED`.
- PostgreSQL constrains both vocabularies and permits only one pending request for
  the same workflow, type, artifact ID, and version.
- Every request stores the artifact ID, exact version, and content hash.
- An architecture checkpoint atomically creates the request and changes a running
  workflow to `WAITING_FOR_APPROVAL`.
- A stage cannot transition to `RUNNING` while its workflow waits for approval.
- The POST approval API requires the pending approval ID, exact artifact ID and
  version, optimistic workflow version, and a separately authenticated reviewer.
- Approval resumes the workflow when no other request is pending. Rejection keeps
  the workflow waiting and cannot later be overwritten by approval.
- A mismatched artifact version returns `409` and preserves the pending decision.
- Creating a newer version of the same logical artifact invalidates older pending
  or approved decisions and appends an audit event.
- Completion requires verified release gates plus a current exact-version
  `RELEASE` approval.

These assertions do not claim production identity integration, clarification
handling, scheduler execution, policy-driven approval selection, or a live model
workflow.
