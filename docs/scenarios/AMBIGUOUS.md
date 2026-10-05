# Ambiguous requirement scenario

The input is `Make links safer.` The deterministic RequirementAgent fixture reports blocking ambiguity and asks about malicious destinations, HTTPS enforcement, automatic expiration, authentication, private-network URLs, and short-code anti-enumeration.

`AmbiguousScenarioIT` persists the requirement and analysis, inserts the clarification checkpoint, and verifies the workflow enters `WAITING_FOR_CLARIFICATION`. The implementation stage stays `BLOCKED` and has no start time. The answer fixture supplies one explicit response for every question; the existing clarification integration test verifies exact-artifact answer submission, immutable clarification and requirement versions, stale prior work, and requirement re-analysis in the new generation.

`ReplanningScenarioIT` exercises the separate `404` to `410 Gone` change. It verifies that expiry-dependent architecture, implementation, tests, and documentation become stale, the old architecture approval becomes invalid, independent analytics stays active, and planning resumes at the affected closure. `FailureRecoveryScenarioIT` and `ParallelJoinScenarioIT` cover fallback recovery and delayed fan-in.

Run the related PostgreSQL tests with:

```sh
UV=/absolute/path/to/uv scripts/test-postgres.sh \
  tests/test_zz_required_scenarios.py::AmbiguousScenarioIT \
  tests/test_replanning.py::ReplanningScenarioIT \
  tests/test_fallback.py::FailureRecoveryScenarioIT \
  tests/test_synchronization_joins.py::ParallelJoinScenarioIT -q
```

No safety interpretation is silently chosen before the human clarification checkpoint.
