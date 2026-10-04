# Phase 10–11 verification assertions

- Eight specialist outputs validate against strict Pydantic and SDK schemas.
- All requested fields for requirements, planning, architecture and implementation
  are present; extra fields such as workflow status are rejected.
- Blocking ambiguity requires ambiguity text and clarifying questions.
- Task graphs reject unknown IDs, duplicate IDs, cycles and dependent parallel groups.
- Fake calls are repeatable, isolated from fixture/result mutation and explicitly labeled.
- Missing fake fixtures and malformed outputs fail.
- The real SDK Runner loops through an authorized artifact tool and parses final output
  against a local scripted Model. HTTP requests are denied in these tests.
- Repeated SDK tool calls exhaust the configured turn ceiling.
- Unknown workflow-status tools fail; requested grants exceeding a role's allowlist fail.
- Deadline expiry is classified; cancellation propagates.
- Provider HTTP/network errors are classified, raw error messages are suppressed,
  and no provider retry or fake substitution occurs.
- Snapshot reads/search are bounded and cannot open host files.
- Cross-context tool reuse and unsupplied artifact/path reads fail.
- All eight specialist calls leave PostgreSQL workflow/stage status, versions and
  audit history unchanged.
- The live smoke was skipped explicitly, not counted as a successful integration.

These assertions describe automated fake/local-SDK and database tests.
They are not evidence of a generated candidate, passing candidate tests,
a security scan, human approval or a live model workflow.

