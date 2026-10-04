# Phase 12 verification assertions

- `GateResult` exposes exactly `PASS`, `FAIL`, and `WAIT`.
- Gates consume frozen evidence snapshots and never receive persistence sessions or
  workflow mutation capabilities.
- Artifact evidence must be current, match its canonical SHA-256, and validate
  against the relevant strict Pydantic specialist output.
- Requirement exit requires a normalized requirement, non-empty acceptance
  criteria, explicit ambiguity status, and assumptions.
- Architecture entry waits for requirement/plan evidence and for clarification of
  blocking ambiguity; a malformed or empty plan fails.
- Architecture exit requires components, API impact, data impact, security,
  failure modes, tests, and tradeoffs.
- Implementation entry passes only an APPROVED architecture decision whose
  artifact ID, version, and hash exactly match the current architecture artifact.
- Release readiness requires successful current build, unit-test,
  integration-test, security-validation, and documentation-finalization evidence.
- Missing or active release prerequisites wait; terminal failure/stale evidence
  and active blocking policy violations fail.
- The default DAG invokes the aggregate release-readiness prerequisite gate.

These assertions are deterministic unit-test evidence. They do not show stage
execution, a human-authenticated approval, policy-rule evaluation, or durable gate
evaluation/audit persistence.
