# Ambiguous requirement checkpoint verification assertions

- `RequirementAgent` instructions identify “Make links safer” as too broad for
  safe planning without human policy choices.
- The structured fake-provider result sets `blocking_ambiguity=true` and asks
  about malicious destinations, HTTPS enforcement, automatic expiration,
  authentication, private-network URLs and anti-enumeration.
- The orchestrator persists the exact analysis and pending clarification,
  completes requirement analysis, creates the conditional clarification stage,
  and atomically transitions `RUNNING → WAITING_FOR_CLARIFICATION`.
- While paused, the scheduler executes no stage and the orchestrator rejects an
  implementation start. No architecture or implementation executor is invoked.
- `POST /api/v1/workflows/{workflowId}/clarifications` requires authenticated
  human identity, exact clarification artifact version, every pending question,
  nonblank answers and an optional optimistic workflow version.
- Human submission preserves Clarification V1 and Requirement V1, creates V2 of
  each, and stores `SUPERSEDES` plus answer-to-requirement `DERIVED_FROM`
  lineage.
- Generation-1 downstream attempts become `STALE`. Generation 2 explicitly
  preserves validated intake and exposes only `REQUIREMENT_ANALYSIS` as ready.
- The post-clarification scheduler cycle invokes requirement analysis exactly
  once and never invokes implementation.
- `CLARIFICATION_REQUESTED`, `REPLAN_STARTED`, `CLARIFICATION_SUBMITTED` and
  `REPLAN_COMPLETED` retain causal audit history.

This evidence does not claim live-model behavior, a completed revised
architecture, release approval, or the complete packaged Phase 25 demo.
