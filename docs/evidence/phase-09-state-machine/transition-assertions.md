# Phase 9 transition assertions

- Required legal stage transitions pass: PENDING → BLOCKED, BLOCKED → READY,
  READY → RUNNING, RUNNING → SUCCEEDED, RUNNING → FAILED,
  FAILED → RETRY_PENDING, and SUCCEEDED → STALE.
- Every workflow and stage enum member has an explicit legal-target set.
- Illegal transitions leave status and version unchanged and append no
  transition audit event.
- Accepted transitions record entity, before/after states, actor, optional
  reason/trace and resulting version.
- An injected audit-store exception rolls back the status and version change.
- Stale expected versions fail before mutation.
- Public ORM status properties are read-only; guarded internal changes outside
  WorkflowOrchestrator fail.
- Transition actors are SYSTEM or HUMAN. AGENT is rejected.
