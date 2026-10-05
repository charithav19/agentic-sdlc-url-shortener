# Requirement Traceability Matrix

Baseline: 2026-10-04. Read with [IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md).

**Phases 1–9, the requested Phase 12–22 scopes, and the deterministic Phase 23–25 scenario fixtures are verified. Phases 10–11 have tested provider/specialist contracts; full-plan live acceptance remains IN_PROGRESS. Candidate assembly, Phase 18 decision/API work, Phase 19 aggregate release rerun, deployed CLI/API coverage, live engineering evidence, and Phases 26–28 remain open.** The tables describe complete scope; verification records below identify actual coverage. No live SDK run or performance result is claimed.

## Sources and notation

- Primary assignment: `docs/schwab-assignment.pdf`, three pages, read completely including page footers. Page/section references below identify the source requirement; requirement IDs are assigned by this plan for tracking, not printed IDs from Schwab.
- Implementation contract: `docs/IMPLEMENTATION_SPEC.md`, version 1.0, sections 1–20, read completely. Its details refine the assignment and are traced separately below so they are not misattributed to Schwab.
- Repository rules: `AGENTS.md`, read completely. Source paths/hashes and reconciliation notes appear in the implementation plan.
- `Pnn` identifies implementation phase nn. Test prefixes `JT/` and `OT/` expand exactly as defined in the plan. A suffix after `::` is a planned behavioral case, not an existing test result.
- Evidence IDs `E01`–`E16` refer to the catalog below. Each evidence bundle must include `docs/evidence/<run-id>/manifest.json`. Replace `<run-id>` with an actual recorded run; never create a success-looking placeholder.
- Each row's final evidence update must include commit, module, exact command/test selector, outcome, report link, demonstration link, provider mode and outstanding limitations. Shared test files are intentional; cases distinguish assertions.

## Phases 23–25 scenario verification record

The deterministic scenario fixtures are **VERIFIED on 2026-10-05**. The
[scenario evidence manifest](evidence/phases-23-25-scenarios/manifest.json)
records 54 passing PostgreSQL tests, 252 passing offline tests, three passing
seed tests, and 37 passing URL-shortener tests.

| Schwab requirement | Implementation phase | Test | Demonstration evidence |
|---|---|---|---|
| SW-01, SW-05, SW-12, SW-41 | P23 greenfield fixture, DAG harness and artifact lineage | `GreenfieldScenarioIT::test_complete_requirement_to_release_path` | Minimal seed, requirement/plan/architecture artifacts, exact architecture and release approvals, both overlapping fan-outs, joins, documentation and completed release in [GREENFIELD.md](scenarios/GREENFIELD.md) |
| SW-06, SW-11, SW-35, SW-41 | P24 brownfield seed and source impact analyzer | `BrownfieldScenarioIT::test_source_driven_impact_and_complete_release_path`; rename-proof impact test; `CoreRegressionTest` | Exact inspected controller/service/domain/repository/redirect/migration/test/OpenAPI paths and preserved core regression in [BROWNFIELD.md](scenarios/BROWNFIELD.md) |
| SW-08, SW-09, SW-41 | P25 ambiguity checkpoint | `AmbiguousScenarioIT::test_pauses_for_clarification_before_any_implementation`; existing clarification integration | Six safety question categories, persisted wait state, blocked unstarted implementation and versioned answer fixture in [AMBIGUOUS.md](scenarios/AMBIGUOUS.md) |
| SW-34, SP-26 | P19/P25 selective replanning fixture | `ReplanningScenarioIT::test_selective_replanning_preserves_unaffected_work` | Affected architecture/code/tests/docs stale, approval invalid, independent analytics active, planning resumed |
| SW-17, SW-18, SW-23 | P14–16 failure and synchronization fixtures | `FailureRecoveryScenarioIT`; `ParallelJoinScenarioIT` | Preserved attempts and labeled fallback; delayed test design keeps build blocked until the join completes |

The specialist content in these scenarios uses the deterministic fake provider.
It verifies orchestration, persistence and governance and is not represented as
a live model-authored code change. The live engineering workflow remains open.

## Schwab assignment requirements → phases → tests → demonstration evidence

| ID | Schwab requirement and source | Implementation phase and owning module | Planned test / review assertion | Planned demonstration evidence |
|---|---|---|---|---|
| SW-01 | Turn a requirement into a reviewable engineering outcome through multi-step agentic execution (p1 §1) | P10–15, P22–23; `agents/`, `orchestration/`, scenario runner | `OT/scenarios/test_greenfield.py::requirement_to_approved_candidate`; `OT/live/test_live_engineering_workflow.py::real_changes_and_execution` | E02 + E15: input, normalized requirement, plan, actual diff, validation and release manifest; fake/live clearly separated |
| SW-02 | Build a URL shortener from scratch with core APIs (p1 §2) | P2, P23; Java API/services, greenfield seed | `JT/LinkApiTest.java`: create/metadata/redirect/missing; greenfield candidate contract checks | E01 + E02: HTTP transcript and seed-to-candidate diff |
| SW-03 | Include analytics (p1 §2) | P4, P23; Java `analytics/` | `JT/AnalyticsTest.java`: successful redirects and UTC daily totals; `AnalyticsFailureIsolationTest.java` | E01: counts and forced analytics failure with successful redirect |
| SW-04 | Include reliability features (p1 §2) | P3–4; URL reliability services | `JT/CollisionTest.java`, `IdempotencyTest.java`, `ExpiryTest.java`, `RateLimitTest.java` | E01: collision bounds, concurrent duplicate creation, expiry and throttling reports |
| SW-05 | Greenfield scenario for new systems/features (p1 §3; p2 §5) | P23; `scenarios/greenfield/` | `OT/scenarios/test_greenfield.py::minimal_seed_to_working_service` | E02: decomposition, orchestration, approvals and actual validation |
| SW-06 | Brownfield enhancements/refactors/bug-fix scope (p1 §3; p2 §5) | P24; `scenarios/brownfield/` | `OT/scenarios/test_brownfield.py::enhancement_preserves_regressions_and_data` | E03: enhancement scenario, inspected baseline, data-preserving migration, before/after regressions. Enhancement is the chosen required brownfield demonstration, not a claim that every example subtype has its own demo |
| SW-07 | Test and documentation improvements (p1 §3) | P11–12, P15, P23–25; test/documentation specialists and gates | `OT/test_specialist_contracts.py::test_and_documentation_outputs`; scenario generated-test execution and documentation-currentness cases | E02–E04: generated test/doc diffs mapped to criteria and executed validation |
| SW-08 | Well-defined and ambiguous requirements (p1 §3) | P13, P23, P25; clarification service | `OT/test_ambiguous_requirement.py::test_ambiguous_requirement_blocks_downstream_until_clarified`; future packaged scenario test | E04: visible clarification pause and zero downstream execution verified; packaged demo remains open |
| SW-09 | Understand intent, identify ambiguity, normalize engineering problem (p1 §4.1) | P11–13, P25; RequirementAgent/schema | `OT/test_specialist_contracts.py::requirement_fields`; `OT/test_ambiguous_requirement.py::test_ambiguous_requirement_blocks_downstream_until_clarified` | E04: six safety questions, explicit blocking status, human answers and revised immutable requirement |
| SW-10 | Decompose into actionable dependent/sequenced tasks (p1 §4.2) | P7–8, P11; PlanningAgent, graph, resolver | `OT/test_specialist_contracts.py::task_dependencies`; `OT/test_dependency_resolver.py::sequential_and_fan_out` | E02–E04: task plan, impacted components and versioned dependency graph |
| SW-11 | Reason about actual brownfield modules/services/APIs/data flows (p1 §4.3) | P11, P24; search/read tools, architecture specialist | `OT/scenarios/test_brownfield.py::inspection_precedes_plan_and_maps_real_files` | E03: tool inspection receipts, impacted-file map, architecture/API/data-flow explanation |
| SW-12 | Coordinate complete SDLC: requirements, design, implementation, tests, docs, release readiness (p1 §4.4) | P7, P9, P11–15, P23; default graph and orchestrator | `OT/test_graph_validation.py::full_lifecycle_contract`; `OT/scenarios/test_greenfield.py::all_required_stages_complete` | E02 + E05: complete graph and causal execution timeline |
| SW-13 | Non-linear, stateful execution with governance (p1 §4.4) | P6–9, P13–16, P19; persistence/state machine | `OT/test_state_machine.py`; `OT/test_parallel_execution.py`; `OT/test_restart_recovery.py` | E05 + E10 + E12: concurrency, durable pause/restart and replan history |
| SW-14 | Explicit dependency graph (p1 §4.4) | P7; graph loader/config | `OT/test_graph_validation.py::reject_cycles_unknowns_duplicates` | E05: stored graph/hash, rejected invalid graph and displayed dependencies |
| SW-15 | Entry and exit gates (p1 §4.4) | P12; gate registry/evidence validation | `OT/test_gates.py::pass_fail_wait_and_current_evidence` | E06: missing/stale evidence blocks and genuine validated evidence passes |
| SW-16 | Sequential execution paths (p2 continuation §4.4) | P8–9; dependency resolver/state machine | `OT/test_dependency_resolver.py::a_before_b` | E05: B remains blocked until A succeeds |
| SW-17 | Parallel execution paths (p2 §4.4) | P14; scheduler/claims | `OT/test_parallel_execution.py::overlap_and_concurrency_cap`; `OT/test_stage_claims.py::single_active_claim` | E05: real overlapping start/end intervals and bounded active count |
| SW-18 | Synchronization of parallel paths (p2 §4.4) | P8, P15; joins/candidate assembly | `OT/test_synchronization_joins.py::delayed_parent_blocks_join`; `OT/test_candidate_assembly.py::conflicting_overlays` | E05: delayed branch blocks build/final-doc join; compatible candidate assembly manifest |
| SW-19 | Preserve cross-stage context (p2 §4.4) | P6, P10–11, P18; immutable inputs/provider context | `OT/test_lineage.py::test_multi_level_branching_parents_children_and_descendants` | E10: exact requirement/design/candidate/evidence version chain |
| SW-20 | Preserve decision lineage (p2 §4.4) | P6, P18; decisions/lineage | `OT/test_lineage.py::decision_rationale_and_alternatives` | E10: decision tree with reasons, alternatives, actors and source artifacts |
| SW-21 | Human approvals for high-impact actions (p2 §4.4) | P13, P20; approvals/auth/policy | `OT/test_approvals.py`; `OT/test_policy_engine.py::test_high_impact_changes_require_exact_current_approval` | E06 + E09: exact-version decisions before implementation/schema/API changes and release |
| SW-22 | Bounded retries (p2 §4.4) | P16; retry policy/failure classifier | `OT/test_retry_policy.py::test_temporary_failure_retries_once_and_preserves_both_attempts`; `::test_retry_exhaustion_without_fallback_safe_stops` | E07: attempt history, persisted delay, success after transient error and exhaustion stop |
| SW-23 | Fallback (p2 §4.4) | P16; fallback registry | `OT/test_fallback.py::test_real_provider_exhaustion_uses_deterministic_fallback` | E07: labeled configured fallback with source-attempt provenance |
| SW-24 | Rollback (p2 §4.4) | P17; semantic compensation | `OT/test_compensation.py::test_security_failure_rolls_back_candidate_and_preserves_approved_state` | E08: candidate rejected, previous approved reference restored, failed evidence retained and replay idempotent |
| SW-25 | Safe-stop controls (p2 §4.4) | P14, P16–17; cancellation/recovery | `OT/test_safe_stop.py::test_safe_stop_conditions_block_descendants_and_store_action`; `::test_only_human_can_resume_exact_latest_safe_stopped_attempt` | E07–E08: persisted reason, last successful stage, action required and validated recovery |
| SW-26 | Security policy guardrails (p2 §4.4) | P11, P20; runner/tool policy/rules | `OT/test_tools.py`, `test_runner_isolation.py`, `test_policy_engine.py`, `test_guardrail_abuse.py` | E09: denied paths/secrets/commands/injection, runner restrictions and structured policy records |
| SW-27 | Compliance and change-control policy guardrails (p2 §4.4) | P13, P19–20; versioned policies/approvals/replan | `OT/test_policy_engine.py::test_high_impact_changes_require_exact_current_approval`; `OT/test_replanning.py` | E06 + E09 + E10: rule/version decisions and exact renewed approval on affected changes; scope explicitly local, no regulatory certification claimed |
| SW-28 | Audit-grade observability and traceability (p2 §4.4) | P6, P9, P18, P21; atomic audit/lineage | `OT/test_transition_atomicity.py`; `OT/test_audit_coverage.py::all_event_types_causal_order_redaction` | E11: sanitized causal audit with actors, versions, reasons and trace IDs; atomicity fault report |
| SW-29 | Success rate metric (p2 §4.4) | P21; `observability/metrics.py`, `reporting.py` | `OT/test_metrics.py::test_required_metrics_and_ratios_use_documented_denominators`; `::test_zero_denominators_render_as_nan_and_histograms_are_empty` | E11: completed/(completed+failed), all-time cohort and N/A/NaN behavior |
| SW-30 | Retry frequency metric (p2 §4.4) | P16, P21 | `OT/test_metrics.py::test_required_metrics_and_ratios_use_documented_denominators` | E11: durable retry-event count divided by every started stage attempt |
| SW-31 | Rollback frequency metric (p2 §4.4) | P17, P21 | `OT/test_metrics.py::test_required_metrics_and_ratios_use_documented_denominators` | E11: distinct terminal workflows with compensation divided by terminal workflows |
| SW-32 | MTTR metric (p2 §4.4) | P16, P21 | `OT/test_metrics.py::test_required_metrics_and_ratios_use_documented_denominators` | E11: first controlled failure to next logical-stage success; unresolved incidents separate |
| SW-33 | End-to-end latency metric (p2 §4.4) | P21 | `OT/test_metrics.py::test_required_metrics_and_ratios_use_documented_denominators`; PostgreSQL endpoint test | E11: creation-to-terminal histogram including workflow waits |
| SW-34 | Dynamic replanning on upstream changes while preserving governance (p2 §4.4) | P18–19, P25; impact/replan/generation fencing | `OT/test_replanning.py::test_requirement_update_selectively_stales_descendants_and_returns_to_planning`; `OT/test_replan_races.py::obsolete_result_rejected` | E04 + E10: 404→410 update, stale descendants/approvals and analytics reuse verified; renewed aggregate validation/release remains open |
| SW-35 | Produce quality code, API/schema definitions, unit/integration tests and docs (p2 §4.5) | P2–4, P11–12, P23–24, P27–28 | `JT/LinkApiTest.java`, `LinkPersistenceTest.java`; all candidate tests; CI build/lint and review | E01–E03 + E14: actual code/migration/OpenAPI/test/doc diffs and executable reports |
| SW-36 | Identify risks/tradeoffs/failure scenarios and validation/safety guardrails (p2 §4.6) | Every phase's risks; P12, P16–17, P20, P28 | Gate/retry/compensation/abuse tests; `docs/FINAL_REVIEW.md` risk-to-test review | E06–E09 + E16: fault-injection outcomes, ADR consequences and explicit limitations |
| SW-37 | Agents execute multi-step work; humans retain oversight/approvals/final quality (p2 §4.7; p3 §7) | P9–13, P20, P23, P28 | `OT/test_state_machine.py::agent_cannot_transition`; `OT/test_reviewer_auth.py`; live workflow approval checkpoints | E02 + E06 + E15: agent tool work bounded by deterministic engine and authenticated decisions |
| SW-38 | Final summary with plan/rationale, artifacts, risks/tradeoffs/validation, assumptions, limitations (p2 §4.8) | P28; `docs/FINAL_ENGINEERING_SUMMARY.md` | Final review confirms every named section and resolves each statement to report/artifact or limitation | E16: final summary, ADRs and traceability audit |
| SW-39 | Runnable end-to-end working prototype (p2 §5) | P23–27; Compose/CLI/scenarios | `scripts/test-compose.sh`; `scripts/smoke-test.sh`; all three scenario tests | E13 + E14: clean-start command transcript, health, workflow completion and CI run |
| SW-40 | Architecture overview: components, orchestration, control flow, decisions (p2 §5) | P1, P7, P9, P18, P28; ADRs/architecture docs | Graph validation + manual diagram/module/API consistency review | E16: implementation-matching architecture/DAG/state/trust-boundary diagrams and ADRs |
| SW-41 | Three scenarios, each showing decomposition, orchestration and validation (p2 §5) | P23–25 | `OT/scenarios/test_greenfield.py`, `test_brownfield.py`, `test_ambiguous.py` | E02–E04: three separately reproducible complete evidence bundles |
| SW-42 | Setup instructions (p2 §5) | P26, P28; README/Make/Compose | Clean-checkout rehearsal of every quick-start command | E13: environment, prerequisites, startup/readiness, CLI invocation and restart transcript |
| SW-43 | Testing approach, limitations and tradeoffs (p2 §5) | P27–28; TESTING/LIMITATIONS/ADRs | Final review distinguishes deterministic/live tests, actual results, exclusions and residual risks | E14–E16: test reports, live evidence, testing/limitations documents |
| SW-44 | Effective orchestration and depth of decomposition/execution (p2 §6) | P7–19, P23–25 | Scenario task mappings, joins, recovery and replan tests reviewed together | E02–E10: reviewer can follow decisions and non-linear execution, not merely a linear transcript |
| SW-45 | Architecture quality, modular/testable/reliable/secure/scalable design and safe change management (p2 §6) | P1–6, P11–21, P24, P26–28 | Service ownership/DB isolation, concurrency, migration/regression, policy tests and architecture review | E03 + E05 + E09 + E12–E16: design evidence and limits; per-instance limiter/single-local-stack scaling constraints explicit |
| SW-46 | Realistic outputs, rigorous validation, clear defensible decisions and engineering judgment (p2 §6; p3 §7) | P11–12, P23–28 | Actual build/test/scanner evidence; live engineering verification; final traceability review | E14–E16 plus scenario bundles: distinguish proven behavior, failures, assumptions and unverified claims |
| SW-47 | Production-grade approach, output ownership, defined autonomy with human final quality (p3 §7) | P9, P13, P20, P28 | Authority boundary tests; human release approval; final evidence/sign-off review | E06 + E09 + E16: explicit ownership, approval record, maintainability/risk review; no unsupported production certification |

## Implementation specification and repository-rule refinements

These rows trace the selected implementation contract. They must not be represented as literal PDF requirements.

| ID | Contract refinement and source | Phase / module | Planned test | Planned demonstration evidence |
|---|---|---|---|---|
| SP-01 | Java 21/Spring Boot 3.x; Python 3.12+/FastAPI; real Agents SDK; PostgreSQL; Typer/Rich; Compose; separate service ownership (spec §2; AGENTS) | P1–6, P10, P22, P26 | Bootstrap/DB isolation/provider/CLI/Compose tests | E13–E15 + architecture review E16 |
| SP-02 | Pin versions; prohibit extra infrastructure/frontend; secrets/workspaces ignored (spec §2–3; AGENTS) | P1, P26–28 | Build lock verification, dependency/secret scan, configuration review | E14 + E16 |
| SP-03 | Product HTTP statuses/metadata/soft-disable contract (spec §4.1) | P2–3; Java controllers | `JT/LinkApiTest.java`, `DisableLinkTest.java`: 201/302/404/410/204 and repeated disable | E01 |
| SP-04 | Seven-character secure Base62; DB uniqueness; five total collision attempts and transaction recovery (spec §4.2) | P2–3 | `JT/CollisionTest.java`: forced collisions and exhaustion on PostgreSQL | E01 collision report |
| SP-05 | Alias format/length/case/reserved names and duplicate 409 (spec §4.2) | P3 | `JT/AliasTest.java`: all boundary/constraint cases | E01 + E03 |
| SP-06 | Future UTC expiry, exact-boundary 410 without cleanup dependence (spec §4.2) | P3 | `JT/ExpiryTest.java`: controlled clock before/at/after expiry | E01 + E03 |
| SP-07 | Durable scoped idempotency, changed-payload conflict, concurrent single creation and retention (spec §4.2) | P3 | `JT/IdempotencyTest.java`: concurrent same and conflicting payloads | E01 DB concurrency report |
| SP-08 | Absolute HTTP/HTTPS URL validation; reject credentials/control characters; no destination fetch (spec §4.2) | P2 | `JT/UrlValidationTest.java` | E01 validation transcript |
| SP-09 | Bounded per-instance in-memory creation limiter, 429 and Retry-After, restart limitation (spec §4.2) | P3 | `JT/RateLimitTest.java`: capacity/window/eviction/reset | E01 + limitations E16 |
| SP-10 | Analytics UTC aggregation, minimized identifying data, isolated failure/timeout, best-effort loss (spec §4.3) | P4 | `JT/AnalyticsTest.java`, `AnalyticsFailureIsolationTest.java` | E01 |
| SP-11 | Health/readiness/metrics/OpenAPI/structured traceable errors and restricted management (spec §4.3, §13) | P2, P4–5, P21 | `JT/ObservabilityTest.java`; `OT/test_health.py`, `test_workflow_api.py` | E01 + E11 + E13 |
| SP-12 | Durable attempts/states/graphs/artifacts/approvals/decisions/clarifications/audit with UTC/UUID/FKs (spec §5) | P6 | `OT/test_persistence.py` | E10 + E12 |
| SP-13 | Sole deterministic state authority; atomic transition/audit; concurrency checks; explicit terminal states (spec §5.2; AGENTS) | P9 | `OT/test_state_machine.py`, `test_transition_atomicity.py` | E06 + E11 + E12 |
| SP-14 | Full stage graph, contract registry, cycle validation, clarification via new generation (spec §6) | P7–8, P13 | `OT/test_graph_validation.py`, `test_dependency_resolver.py`, `test_clarifications.py` | E04 + E05 |
| SP-15 | Gates need compatible/current/verifiable evidence, not model claims (spec §7.1) | P12, P15 | `OT/test_gates.py`, `test_synchronization_joins.py` | E06 |
| SP-16 | Four approval types; exact artifact version/hash; auth, duplicate decisions, invalidation (spec §7.2) | P13, P19 | `OT/test_approvals.py`, `test_reviewer_auth.py`, `test_replanning.py` | E06 + E10 |
| SP-17 | Eight specialist schemas; bounded tools/turns/time; configurable model; visible provider mode (spec §8.1) | P10–11 | `OT/test_agent_provider.py`, `test_specialist_contracts.py` | E02 + E15 |
| SP-18 | Restricted filesystem tools and actual build/test runner isolation; no host/API/CI secrets (spec §8.2) | P11, P20, P26–27 | `OT/test_tools.py`, `test_runner_isolation.py`, `test_guardrail_abuse.py` | E09 + E13–E14 |
| SP-19 | Configurable bounded asyncio execution, durable claims, restart/cancellation/fencing (spec §9) | P14, P16 | `OT/test_parallel_execution.py`, `test_stage_claims.py`, `test_restart_recovery.py`, `test_safe_stop.py` | E05 + E07 + E12 |
| SP-20 | Isolated overlays, conflict-aware candidate joins, read-only validations, separate build outputs (spec §9) | P11, P15 | `OT/test_candidate_assembly.py`, `test_synchronization_joins.py` | E05 candidate assembly/parallel validation records |
| SP-21 | Two total attempts; classified transient errors; no retry multiplication or uncertain-effect replay (spec §10.1) | P10, P16 | `OT/test_retry_policy.py`; `OT/test_agent_provider.py` | E07 |
| SP-22 | Explicit fallback only, same gates/provenance, no manufactured validation/approval (spec §10.2) | P16 | `OT/test_fallback.py::test_real_provider_exhaustion_uses_deterministic_fallback` | E07 |
| SP-23 | Semantic rollback preserves candidate/evidence; idempotent restore; no prior candidate and compensation-failure cases (spec §10.3) | P17 | `OT/test_compensation.py::test_security_failure_rolls_back_candidate_and_preserves_approved_state` | E08; no-prior and injected compensation-failure variants remain open |
| SP-24 | Safe-stop persists cause/last success/action; no descendants; authenticated validated recovery (spec §10.4) | P16 | `OT/test_safe_stop.py::test_safe_stop_conditions_block_descendants_and_store_action`; `::test_safe_stop_retains_last_successful_stage`; `::test_only_human_can_resume_exact_latest_safe_stopped_attempt` | E07 |
| SP-25 | Immutable hashed artifacts, typed lineage relationships, decisions and exact inputs (spec §11.1; AGENTS) | P6, P18 | `OT/test_artifact_immutability.py`, `test_lineage.py::test_multi_level_branching_parents_children_and_descendants`, `::test_supersedes_requires_newer_exact_version_and_relationships_are_typed` | E10; typed artifact lineage verified, decision lineage remains open |
| SP-26 | Stable requirement/component selective impact; 404→410 example; reuse analytics; renew approvals and aggregate tests (spec §11.2) | P19, P25 | `OT/test_replanning.py::test_requirement_update_selectively_stales_descendants_and_returns_to_planning`, `test_replan_races.py`, scenario ambiguous test | E10 selective invalidation/reuse verified; aggregate rerun and scenario proof remain open |
| SP-27 | Versioned ALLOW/DENY/REQUIRE_APPROVAL policies; instruction injection untrusted; scanner evidence (spec §12) | P11, P20 | `OT/test_policy_engine.py`, `test_guardrail_abuse.py`, `test_gates.py::test_release_failures_are_explained_by_versioned_policy` | E09: Phase 20 policy manifest, assertions and test counts |
| SP-28 | Complete /api/v1 workflow APIs, fast return, invalid/stale rejection, pagination (spec §13.1) | P7, P9, P13, P16, P18–19, P21 | `OT/test_workflow_api.py`, `test_artifact_api.py`, API-specific tests | E06 + E10–E12 |
| SP-29 | All CLI commands, exact approval details, JSON/no-color/narrow display, watch interruption, explicit CI actors (spec §13.2) | P22–25 | `OT/test_cli.py`, `test_cli_api_contract.py`, scenario tests | E02–E04 CLI transcripts |
| SP-30 | Minimal greenfield seed; real generated files/tests/docs; separate live proof (spec §14.1) | P23 | `OT/scenarios/test_greenfield.py`, `OT/live/test_live_engineering_workflow.py` | E02 + E15 |
| SP-31 | Brownfield actual inspection and data-preserving alias/expiry upgrade (spec §14.2) | P24 | `OT/scenarios/test_brownfield.py` | E03 |
| SP-32 | Blocking ambiguity/questions/answers/versioning and failure-injection scenario variants (spec §14.3) | P13, P23–25 | `OT/test_ambiguous_requirement.py::test_ambiguous_requirement_blocks_downstream_until_clarified`; remaining scenario failure variants | E04 ambiguity checkpoint verified; packaged/failure variants remain open |
| SP-33 | Precise metric formulas/windows/N/A, pending gauge, audit event fields/causal sequence (spec §15) | P6, P9, P21 | `OT/test_metrics.py`, `test_audit_coverage.py` | E11 |
| SP-34 | Real PostgreSQL migration/constraint/concurrency tests, deterministic clocks/provider, separate live evidence (spec §16; AGENTS) | P1–28 as applicable | Java PostgreSQL tests; Python integration suite; live smoke and workflow tests | E12 + E14–E15 |
| SP-35 | Durable Compose, health-gated startup, separate roles/migrations, loopback/non-root, graceful stop, fake default (spec §17) | P26 | `scripts/test-compose.sh`, `scripts/smoke-test.sh` | E13 |
| SP-36 | Required Make targets; down preserves data; documented prerequisites/downloads/config (spec §17) | P1 incrementally, P26 | Clean-start and data-survival checks | E13 + E16 |
| SP-37 | 28 ordered phases; implement only requested phase; evidence/status after each; early lineage/policy/audit (spec §18; AGENTS) | Planning; every implementation phase | Plan structure/dependency audit; per-phase completion review | This plan now; actual completion records and E16 later |
| SP-38 | CI build/lint/DB/scenarios/package/smoke/security; least privilege/pinned actions; protected opt-in live (spec §19.1) | P27 | Actual GitHub Actions runs and workflow permission review | E14–E15 |
| SP-39 | Full docs/ADRs/scenario guides/traceability and honest final checklist (spec §19.2–20) | P28 | `docs/FINAL_REVIEW.md`: every checklist item linked to evidence or explicit gap | E16 |

## Demonstration evidence catalog

Paths below are future run outputs. Store reports only after actual execution, sanitized for review. Bundle references may point to multiple runs; every run must say whether its provider is fake, live, or explicit deterministic fallback. A model's narrative is never a substitute for tool receipts or test reports.

| Evidence ID | Planned path under `docs/evidence/<run-id>/` | Minimum content / observable proof |
|---|---|---|
| E01 | `url-api.md`, `url-junit.xml`, `url-migrations.md` | Creation/redirect/metadata/alias/expiry/disable/idempotency/throttle/analytics HTTP results; concurrency/collision/analytics-failure reports; actual PostgreSQL migration outcomes; sensitive URLs sanitized |
| E02 | `greenfield/cli.txt`, `greenfield/changes.patch`, `greenfield/release-manifest.json`, `greenfield/tests.xml` | Minimal seed hash; actual generated code/test/doc diffs; requirement/task/architecture artifacts; approvals; command invocations; final candidate hash; release decision |
| E03 | `brownfield/inspection.json`, `brownfield/changes.patch`, `brownfield/before-tests.xml`, `brownfield/after-tests.xml`, `brownfield/migration.md` | Actual inspected files/API/data flows before planning; approved alias/expiry change; old rows preserved; original regressions plus new tests; no mutation of demonstration seed |
| E04 | `ambiguous/cli.txt`, `ambiguous/requirements.json`, `ambiguous/replan.json`, `ambiguous/tests.xml` | Clarification pause with zero implementation calls; human answers; new analysis generation; expiry change and final 410; stale/reused artifacts/approvals; regenerated validation |
| E05 | `orchestration/graph.json`, `orchestration/timeline.json`, `orchestration/joins.md`, `orchestration/candidate-manifest.json` | Versioned graph; actual stage intervals proving overlap; bounded concurrency; delayed predecessor visibly blocking join; compatible overlay assembly or explicit conflict |
| E06 | `governance/gates.jsonl`, `governance/approvals.jsonl`, `governance/cli.txt` | PASS/FAIL/WAIT with refs; exact-version approvals/rejection/invalidation; high-impact/assumption handling; trusted actor identity; stale evidence and forged approval denied |
| E07 | `recovery/attempts.json`, `recovery/safe-stop.json`, `recovery/tests.xml` | Injected transient cause, two-total-attempt bound and backoff; configured labeled fallback; unsupported fallback stop; no descendant scheduling; fenced late result; validated human resume |
| E08 | `compensation/events.jsonl`, `compensation/candidate-refs.json`, `compensation/tests.xml` | Failed candidate retained, previous-approved reference preserved/restored, dependent approvals invalidated; idempotent replay; no-prior-reference and compensation-failure cases |
| E09 | `policy/decisions.jsonl`, `policy/isolation.md`, `policy/abuse-tests.xml` | Rule/version/action/reason; workspace and runner boundaries, secret exclusion, resource/network limits; prohibited command/impersonation/injection/escape denials; known security gaps |
| E10 | `lineage/graph.json`, `lineage/decisions.json`, `lineage/impact.json` | Exact artifact hashes/versions/input refs/producers; rationales/alternatives; 404→410 affected closure; independently reused analytics; renewed release gates; immutable previous history |
| E11 | `observability/audit.jsonl`, `observability/metrics.prom`, `observability/summary.json`, `observability/reconciliation.md` | All event classes, causal sequence/actors; declared metric windows/cohorts, underlying counts and controlled clock values; N/A handling; unresolved incidents distinct; no workflow-ID metric labels |
| E12 | `persistence/restart.md`, `persistence/concurrency-tests.xml` | PostgreSQL atomic transition/audit failure test; competing claims; stopped/restarted process; approvals and succeeded stages retained; lease reconciliation and uncertain effects handled without blind replay |
| E13 | `compose/clean-start.txt`, `compose/health.json`, `compose/restart.txt`, `compose/smoke.txt` | Fresh checkout prerequisites, build/migrations/readiness, CLI path, loopback services, role separation, runner constraints, durable data after down/up, graceful shutdown |
| E14 | `ci/run.json`, `ci/reports/`, `ci/security-review.md` | Actual commit and CI URL/job outcomes; Java/Python lint/test/integration, fake scenarios, Compose/package/smoke, dependency/secret scans; preserved failed reports and honest skipped checks |
| E15 | `live/sdk-smoke.json`, `live/workflow.json`, `live/changes.patch`, `live/tool-invocations.jsonl`, `live/tests.xml` | Actual configured model/SDK/provider, bounded execution, live output schema validation; real engineering edits, actual commands/tests and human approvals; explicit failed/skipped state if not achieved |
| E16 | `review/final-checklist.md`, `review/walkthrough.txt`, `review/evidence-index.json` | Completed reviewer walkthrough, final engineering summary references, architecture/ADR consistency, requirement coverage, limits/assumptions, source reconciliation and unresolved gaps |

## Acceptance and update rules

1. Do not mark a requirement verified until its implementation, automated test or explicit review, and demonstration evidence exist and match the same relevant candidate/commit. Record mixed outcomes precisely.
2. Keep fake scenario evidence separate from live agent evidence. The live SDK smoke and at least one live engineering workflow are required by the specification; missing credentials do not turn a fake success into live verification.
3. Fault-injection evidence must demonstrate failure behavior, not just assert that recovery code exists. Concurrency requires overlapping measured intervals and synchronization requires a deliberately delayed branch.
4. Generated code is executed only in the restricted runner. Approval decisions come from authenticated humans or explicitly labeled fixture reviewers; agents cannot grant approval.
5. Replanning evidence must show affected descendants stale, affected approvals invalid, unrelated analytics reused, and whole-candidate validation rerun for the new hash. Retaining a file alone does not prove valid selective reuse.
6. Final review addresses every SW/SP row, all specification §20 checklist items, and assignment evaluation criteria. A failed/blocked requirement stays open with its exact reason.
7. The PDF's 2–3 day context is a schedule constraint to discuss, not permission to omit required capabilities. Its internal classification is preserved; no public publication is authorized by this plan.

## Phase 20 policy guardrails verification record

Phase 20 is **VERIFIED on 2026-10-04 for the requested deterministic policy
scope**. Rules are code-owned and versioned; the packaged YAML file contains
metadata only and cannot register executable behavior.

| Requirements | Test evidence | Verified behavior | Remaining integration |
|---|---|---|---|
| SW-26, SP-18, SP-27 | `test_policy_engine.py`, `test_tools.py`, `test_guardrail_abuse.py` | Generated files are workspace-contained and scanned before mutation; traversal, outside writes, credential-like content and arbitrary commands deny; rejected patches preserve the prior file | Replace the lightweight scanner with maintained production scanning and add durable records for every low-level preflight denial |
| SW-21, SW-27, SP-16, SP-27 | `test_high_impact_changes_require_exact_current_approval` plus Phase 13 approval tests | Schema changes require exact current `ARCHITECTURE` approval; breaking API changes require exact current `HIGH_IMPACT_CHANGE` approval; stale versions do not authorize | Production identity/authorization and policy administration |
| SW-12, SW-26, SP-15, SP-27 | `test_release_failures_are_explained_by_versioned_policy` and release gate tests | Mandatory test failures resolve to `MANDATORY_TESTS_PASS@1`; security failures resolve to `SECURITY_RELEASE_BLOCK@1`; either blocks release | Full scenario release assembly and live evidence |
| SW-28, SP-13, SP-27 | PostgreSQL policy audit test and clean migration test | Append-only `policy_events` retain policy/rule versions and sanitized evidence; `POLICY_VIOLATION` is committed atomically and references the policy event | Phase 21 audit query API, complete event coverage and metrics |
| SW-26, SW-36, SP-27 | Instruction/policy-manifest abuse tests | Repository requirements, tool output and generated `policies.yaml` text cannot expand registered actions or grant shell authority | Broader maintained adversarial corpus |

The complete PostgreSQL suite passed 49 tests. The offline suite passed 207
tests with one opt-in live SDK smoke skipped. Phase 20 sources pass Ruff and
formatting; lock, package build, structure and diff checks pass. Repository-wide
Ruff retains three pre-existing line-length findings in `0006_compensations.py`.
See the [Phase 20 policy evidence manifest](evidence/phase-20-policy/manifest.json).

## Phase 21 orchestration metrics verification record

The requested orchestration-metrics scope is **IMPLEMENTED and VERIFIED
OFFLINE on 2026-10-04**. Values are derived from committed PostgreSQL records,
so a process restart cannot reset counters or replay increments. The real
PostgreSQL endpoint test is implemented; execution was blocked because this
sandbox denied Docker socket connections after explicit filesystem grants.

| Requirements | Test evidence | Verified behavior | Remaining integration |
|---|---|---|---|
| SW-29, SW-30, SW-31 | `test_required_metrics_and_ratios_use_documented_denominators` | Success uses completed/(completed+failed); retry frequency uses retries/started attempts; rollback frequency uses terminal workflows with completed compensation/terminal workflows | Execute the committed endpoint test against PostgreSQL outside the current socket restriction |
| SW-32 | Same controlled-clock test plus zero-denominator test | Consecutive failures form one incident; next logical-stage success closes it; unresolved incidents remain separate | Add reporting-window materialization for long retention |
| SW-33, SP-11 | Formula, histogram, and HTTP content tests | Workflow duration starts at first run; end-to-end begins at creation and includes waits; `/metrics` serves Prometheus 0.0.4 | PostgreSQL endpoint execution is pending |
| SW-28 | Durable reporter review and Alembic offline generation | Counters reconstruct from workflow, stage, policy, approval, compensation, and audit records without high-cardinality labels; reporting indexes compile | Phase 21 audit query API and complete cross-feature audit coverage remain open |

The focused offline metrics suite passed four tests. The complete offline suite
passed 211 tests with one opt-in live SDK test skipped. Ruff and formatting pass
for the metrics, API, migration, and test files; Alembic generated the complete
PostgreSQL upgrade SQL through revision `0009_observability_indexes`.
See the [Phase 21 metrics evidence manifest](evidence/phase-21-metrics/manifest.json).

## Phase 22 terminal CLI verification record

The user-requested Phase 22 command surface is **IMPLEMENTED and VERIFIED
OFFLINE on 2026-10-04**. Every command uses the versioned FastAPI HTTP boundary;
the CLI imports no persistence repository or orchestration state authority.

| Requirements | Test evidence | Verified behavior | Remaining integration |
|---|---|---|---|
| SP-01, SP-29 | Parameterized help tests and installed `agentic --help` | Typer exposes workflow create/status/watch/graph, approval list/approve/reject, artifact list/show, lineage, clarification list/answer, requirement update, audit, metrics, and three demo commands | Full-plan resume/cancel commands remain open because they were outside the requested command list |
| SW-21, SW-37, SP-16, SP-29 | Approval confirmation and HTTP contract tests | Exact approval/artifact/workflow versions are posted only after explicit confirmation; rejection requires a reason; reviewer token and identity travel only in headers | Live FastAPI reviewer round trip and production identity |
| SW-28, SW-29–33, SP-29 | Status/graph/lineage/audit/metrics rendering tests | Rich panels, tables, trees and status symbols expose stages, blockers, lineage, audit pages and Prometheus values; JSON and no-color modes remain available | SP-28 read/create API routes and live-server contract coverage |
| SW-05, SW-06, SW-08, SP-29–32 | Demo delegation tests | Demo commands call the workflow API with a server-owned selector and contain no canned outcomes or direct scenario execution logic | Packaged scenario services and evidence arrive in Phases 23–25 |
| SW-45, SP-29 | Structured error, bounded watch, pagination and secret assertions | Connection/4xx/5xx failures have stable exit codes; trace IDs remain visible; watch is bounded and never sends cancellation; secrets are absent from output | Ctrl-C subprocess rehearsal against a live server |

The focused CLI suite passed 41 tests. The complete offline suite passed 252
tests with one opt-in live SDK test skipped. Ruff and formatting pass for all
CLI and CLI-test files; the locked package installs and runs the `agentic`
entry point. See the [Phase 22 CLI evidence manifest](evidence/phase-22-cli/manifest.json).

## Phase 25 ambiguous requirement checkpoint verification record

Phase 25 is **VERIFIED on 2026-10-04 for the requested ambiguity checkpoint
scope**. This is a deterministic fake-provider integration scenario; it is not
the complete packaged Phase 25 demonstration or live-provider evidence.

| Requirements | Test evidence | Verified behavior | Remaining integration |
|---|---|---|---|
| SW-08, SW-09, SP-17, SP-32 | `test_ambiguous_requirement_blocks_downstream_until_clarified` | RequirementAgent returns explicit normalized requirement, criteria, ambiguities, risks, six safety questions and `blocking_ambiguity=true` | Opt-in live-provider scenario evidence |
| SW-13, SW-25, SP-14 | Same PostgreSQL scenario | Workflow transitions `RUNNING → WAITING_FOR_CLARIFICATION`; conditional clarification stage waits; scheduler and direct transition guards prevent architecture/implementation execution | CLI watch/status presentation |
| SW-08, SW-34, SP-25, SP-32 | Clarification API assertions | Exact pending Clarification V1 receives complete human answers in immutable V2; Requirement V2 preserves answers and both supersession chains | Duplicate/concurrent submission fault injection |
| SW-13, SP-13, SP-19 | Generation and scheduler assertions | Old downstream attempts become `STALE`; validated intake is preserved in generation 2 and only requirement analysis reruns | Continue through revised architecture approval and full candidate validation |

The complete PostgreSQL suite passed 47 tests; the offline suite passed 176
tests with one opt-in live smoke skipped. See the [Phase 25 ambiguity evidence
manifest](evidence/phase-25-ambiguity/manifest.json).

## Phase 19 selective dynamic replanning verification record

Phase 19 is **VERIFIED on 2026-10-04 for the requested requirement-update and
selective generation scope**. The endpoint prepares the new generation for the
scheduler; it does not represent completion of that generation's specialist or
validation work.

| Requirements | Test evidence | Verified behavior | Remaining integration |
|---|---|---|---|
| SW-34, SP-26 | `test_requirement_update_selectively_stales_descendants_and_returns_to_planning` | `404` Requirement V1 remains immutable; `410 Gone` becomes V2 with `SUPERSEDES`; request replay with the same update ID returns the same result | Conflicting concurrent update fault injection |
| SW-34, SP-25–26 | Same PostgreSQL scenario | Lineage and DAG closure stale architecture, implementation, expiry tests and API documentation while analytics remains active and its stage remains succeeded | Explicit persisted reuse-reference record beyond unchanged lifecycle |
| SW-21, SW-34, SP-16 | Same PostgreSQL scenario | Exact Architecture V1 approval becomes `INVALIDATED`; generation 2 contains a blocked architecture approval stage requiring a new architecture version | Execute design and obtain renewed human decision |
| SW-13, SW-28, SP-13, SP-19 | Stage and audit assertions | Old affected attempts become `STALE`, generation increments, and task decomposition alone is `READY`; ordered `REPLAN_STARTED`/`REPLAN_COMPLETED` events retain the impact set | Inject an in-flight old-generation result, then execute aggregate validation and renewed release gate |

The complete PostgreSQL suite passed 46 tests; the offline suite passed 176
tests with one opt-in live smoke skipped. See the [Phase 19 evidence
manifest](evidence/phase-19-replanning/manifest.json).

## Phase 18 artifact versioning and lineage verification record

Phase 18 is **VERIFIED on 2026-10-04 for the requested artifact versioning and
lineage scope**. The result exposes a typed application service; the planned
HTTP inventory/query API and decision-lineage work remain open.

| Requirements | Test evidence | Verified behavior | Remaining integration |
|---|---|---|---|
| SW-19, SP-25 | `test_multi_level_branching_parents_children_and_descendants` | Requirement → Plan → Architecture branches to Code, Test Plan, and Documentation; direct parents/children and deterministic transitive descendants retain exact versions, hashes and stable requirement/component IDs | Bind lineage query results to specialist producer-attempt context and HTTP API |
| SW-19, SP-25 | Both PostgreSQL lineage scenarios plus persistence isolation tests | All five relationships are typed; self, cross-workflow and cycle-producing edges are rejected; repeated identical edge creation is idempotent | Phase 19 impact analysis and stale-descendant propagation |
| SP-25 | `test_supersedes_requires_newer_exact_version_and_relationships_are_typed` and artifact immutability suite | Immutable v1/v2 artifacts are connected by `SUPERSEDES`; reversed version order and unknown relationships are rejected | Lifecycle history/API and decision lineage |
| SW-28, SP-13 | Migration and audit assertions | DB vocabulary constraint, parent/child indexes, historical `REVISES` normalization and lineage-creation audit payload are persisted transactionally | Phase 21 audit query/metrics |

The complete PostgreSQL suite passed 45 tests; the offline suite passed 176
tests with one opt-in live smoke skipped. See the [Phase 18 evidence
manifest](evidence/phase-18-lineage/manifest.json).

## Phase 17 semantic rollback verification record

Phase 17 is **VERIFIED on 2026-10-04** for the requested semantic candidate
rollback scenario. The behavior is PostgreSQL-backed compensation; it does not
represent distributed database, deployment or migration rollback.

| Requirements | Test evidence | Verified behavior | Remaining integration |
|---|---|---|---|
| SW-24, SP-23 | `test_security_failure_rolls_back_candidate_and_preserves_approved_state` | Succeeded implementation candidate enters validation; injected security rejection marks it `ROLLED_BACK`; immutable payload remains inspectable | No-prior-approved candidate variant |
| SW-24, SP-23 | Same PostgreSQL scenario and replay assertion | Prior approved pointer, lifecycle and exact release approval remain active; duplicate compensation returns the original record and emits no duplicate rollback events | Crash-after-start recovery injection |
| SW-28, SP-13 | Ordered audit assertions | `ROLLBACK_STARTED` and `ROLLBACK_COMPLETED` contain candidate, cause, compensation ID and restored reference in one transaction | Phase 21 audit API/metrics |
| SW-25, SP-24 | Scheduler recovery assertion | Compensation completes before existing security safe-stop; workflow and failed validation stage stop after the approved reference is restored | Recursive derived-evidence invalidation in Phase 18 |

The complete PostgreSQL suite passed 43 tests. See the
[Phase 17 evidence manifest](evidence/phase-17-compensation/manifest.json).

## Phase 16 retry, fallback and safe-stop verification record

Phase 16 is **VERIFIED on 2026-10-04** for the requested recovery scope. The
tests use real PostgreSQL transactions and injected typed failures; no live
provider call is represented as recovery evidence.

| Requirements | Test evidence | Verified behavior | Remaining integration |
|---|---|---|---|
| SW-22, SP-21 | `test_retry_policy.py` and retry classifier cases | Default two total primary attempts; deterministic bounded delay; timeout/provider/workspace failures alone retry; every attempt retained | Scheduler daemon timing and uncertain-effect reconciliation |
| SW-23, SP-22 | `test_real_provider_exhaustion_uses_deterministic_fallback` | Fallback starts only after two transient primary failures; separate attempt, executor, claim state and source provenance | Live provider failure demonstration and full gate binding |
| SW-25, SP-24 | Parameterized safe-stop injections and descendant assertions | Policy, assertion, invalid requirement, security, forbidden tool, invalid state and corrupt lineage do not retry; stage/workflow stop atomically; descendants receive no claim | General workflow status/read API and operational runbook |
| SW-25, SP-24, SP-28 | Human recovery and request-schema tests | Explicit resolved cause, authenticated human actor, optimistic workflow version, exact latest stopped attempt and current artifact inputs required; recovery creates a new attempt | Production identity provider and broader policy reevaluation |
| SW-28, SP-13 | Retry/fallback/safe-stop audit assertions | Causal events retain failure code, reason, attempt, fallback source and recommended action alongside state changes | Phase 21 audit query and reliability metrics |

Ruff and formatting checks passed, 176 offline tests passed, all 42 PostgreSQL
integration tests passed, and the Python source/wheel packages built. See the
[Phase 16 evidence manifest](evidence/phase-16-recovery/manifest.json).

## Phases 14–15 parallel execution and synchronization verification record

Phases 14–15 are **VERIFIED on 2026-10-04** for the requested bounded execution,
duplicate-claim prevention, two fan-outs, and mandatory build synchronization.
The tests use real PostgreSQL transactions and controlled asyncio barriers.

| Requirements | Test evidence | Verified behavior | Remaining integration |
|---|---|---|---|
| SW-17, SP-19 | Two parameterized fan-out tests | All three architecture children and all three post-build validators overlap | Scheduler daemon lifecycle and restart recovery |
| SW-17, SP-19 | `test_scheduler_never_exceeds_configured_concurrency` | Three ready stages run with observed maximum two when configured to two | Runtime metrics and dynamic operational controls |
| SW-18, SP-20 | `test_build_waits_for_delayed_test_design_then_becomes_ready` | Fast implementation cannot release build; delayed test design success changes build `BLOCKED → READY` | Candidate version compatibility and overlay assembly |
| SW-13, SP-19 | `test_competing_schedulers_cannot_duplicate_a_stage_claim` | Two schedulers produce one UUID-fenced claim, one execution, one commit | Lease heartbeat and uncertain-effect recovery |
| SW-28, SP-33 | Claim/readiness audit assertions | Claim, completion and join status events carry stage/generation/attempt and before/after state | Full metrics and audit API in Phase 21 |

The focused suite passed five PostgreSQL tests, the complete PostgreSQL suite
passed 29, and the offline suite passed 164 with one opt-in live smoke skipped.
See [the Phases 14–15 evidence manifest](evidence/phase-14-15-parallel-joins/manifest.json).

## Phase 13 approval verification record

Phase 13 is **VERIFIED on 2026-10-04** for the requested human-approval
checkpoint scope. PostgreSQL tests demonstrate that architecture and release
requests pause the workflow, a matching human approval resumes it, rejection
keeps it blocked, wrong versions return `409`, and newer artifact versions
invalidate older approvals. `WorkflowOrchestrator` also rejects stage start
while waiting and requires a current exact-version release approval before
completion.

| Requirements | Test evidence | Verified behavior | Remaining integration |
|---|---|---|---|
| SW-21, SP-16 | `test_approvals.py` pause/resume/version/invalidation cases | Four types/statuses; exact ID/version/hash record; stale invalidation; rejection blocks | Policy-driven high-impact/assumption selection in Phase 20 |
| SW-37, SP-13 | Stage-start and reviewer credential tests | Only orchestrator changes status; waiting workflow cannot start work; separate local human token | Production identity/authorization hardening |
| SW-12, SP-15 | Release checkpoint/completion test | Release pauses before completion; current exact approval and verified release gates are both required | Scheduler and complete release evidence assembly |
| SW-28, SP-33 | PostgreSQL audit assertions | Request, decision, invalidation, pause, and resume events persist transactionally | Full audit projections and metrics in Phase 21 |

The offline suite passed 164 tests with one opt-in live skip; the PostgreSQL
suite passed 24 tests. Clarification handling, approval listing, full policy
selection, and selective lineage invalidation were outside this request. See
[the Phase 13 evidence manifest](evidence/phase-13-approvals/manifest.json).

## Phase 12 verification record

Phase 12 is **VERIFIED on 2026-10-04** for the requested deterministic entry and
exit gate scope. `test_gates.py` verifies the exact `PASS`/`FAIL`/`WAIT`
vocabulary and all requested gate inputs. Requirement and architecture exits
validate hashed specialist artifacts and mandatory sections. Architecture entry
waits for a normalized requirement and valid task plan and cannot pass blocking
ambiguity. Implementation entry requires an `APPROVED` architecture decision
bound to the current artifact ID, version, and hash. Release readiness aggregates
current successful build, unit, integration, security, and documentation evidence
and fails on active blocking policy violations.

| Requirements | Test evidence | Verified behavior | Remaining integration |
|---|---|---|---|
| SW-15, SP-15 | `test_gates.py` (28 tests) and `test_graph_validation.py` release assertion | Typed gates reject missing, malformed, corrupt, stale and incompatible evidence; WAIT never becomes PASS | Scheduler claim/commit recheck and durable gate/audit record |
| SW-09 | Requirement/architecture-entry gate tests | Normalized requirement, acceptance criteria, explicit ambiguity/assumptions; blocking ambiguity waits | Clarification persistence/resume is now verified in the Phase 25 requested scope |
| SW-21, SP-16 | Implementation-entry approval tests | Only an exact current APPROVED architecture artifact passes | Reviewer authentication/API/invalidation in Phase 13 |
| SW-12, SP-15 | Release-readiness tests | Build, unit, integration, security and documentation must all succeed; blocking policy finding fails | Policy engine rules in Phase 20 and scheduler execution in Phase 14 |

The focused gate/graph suite passed 42 tests; the complete default orchestrator
suite passed 162 tests with 26 explicitly configured integration, runner, and
live checks skipped. Ruff passed. This phase does not claim scheduler execution,
durable gate evaluation storage, human authentication, or live agent quality.
See [the Phase 12 evidence manifest](evidence/phase-12-gates/manifest.json).

## Phase 11 bounded engineering tools follow-up

The [bounded-tool evidence](evidence/phase-11-engineering-tools/manifest.json)
records **159 passed tests** (134 unit, 18 PostgreSQL, seven real Docker runner)
and one opt-in live smoke skip. This verifies the seven requested tools.

| Requirement | Implementation | Test | Demonstration evidence |
|---|---|---|---|
| SW-11, SW-35, SP-18 | Workspace read/search/write/patch | `test_files_write_read_search_patch_and_archive` | Real edited file and changed SHA; deterministic archive |
| SW-26, SP-18, SP-27 | UUID ownership and descriptor-based path checks | `test_forbidden_paths_for_every_file_operation`, cross-workflow/link/secret tests | Traversal, outside paths, credentials, links and special files denied |
| SW-35, SP-18 | Exact command profiles and isolated runner | Java test/package and pytest runner tests | All three commands executed successfully in disposable containers |
| SW-26, SP-18 | Container inspection and runtime restrictions | `test_pytest_isolation_and_no_host_effects` | No host credentials/socket/mounts/network; non-root and resource controls observed |
| SW-36, SP-18 | Deadline/output limits and cleanup | Failure, timeout, output-limit, cancellation, inspection-rejection tests | Actual failure classifications and no remaining candidate containers |
| SW-37, SP-13, SP-17 | SDK grants and workspace allocation | SDK permissions/receipts and PostgreSQL state-boundary tests | Tool receipts plus UUID workspace; workflow status remains unchanged |

Durable tool invocation storage, retained build products, parallel overlays
and live engineering evidence remain open. Earlier records below describe
the original delivery before this follow-up.

## Phase 10–11 verification record

The [agent evidence manifest](evidence/phase-10-11-agents/manifest.json)
records 105 passing tests and one opt-in live skip. These are offline
fixture/local-SDK and PostgreSQL results, not a live model demonstration.

| Requirement | Phase/module | Tests | Actual evidence / outstanding scope |
|---|---|---|---|
| SW-09, SP-17 | P11 RequirementAgent | `test_specialist_contract`, `test_blocking_ambiguity_requires_questions`, `test_ambiguous_requirement_blocks_downstream_until_clarified` | Strict requirement fields, blocking ambiguity output and human clarification workflow verified with fake provider; live quality remains open |
| SW-10, SP-17 | P11 PlanningAgent | `test_invalid_task_graph` | Task references/cycles/parallel groups validated; live decomposition quality unverified |
| SW-07, SW-11, SW-12, SP-17 | P11 eight specialists | `test_specialist_contract`, `test_specialists_bind_existing_graph_identifiers` | Instructions, schemas, tools and budgets for all eight; candidate editing/execution pending |
| SW-19, SP-17 | P10 context/provider | `test_fake_provider_repeatable_and_validated` | Versioned bounded inputs and provenance hashes; durable result integration pending |
| SW-37, SP-13 | P10–11 authority boundary | `test_specialists_leave_state_and_audit_unchanged`, forbidden SDK tool call test | PostgreSQL state/version/audit unchanged; no mutation/approval tools |
| SP-18, SP-27 | P11 snapshot tools | `test_snapshot_tools.py` | Supplied-snapshot reads only, unauthorized paths/contexts denied; host runner and write tooling unimplemented |
| SP-21, SP-34 | P10 SDK adapter | SDK loop/failure/timeout/cancellation/error tests | Real SDK exercised with local inference stub; no automatic retries or fake fallback |
| SP-34 | P10 live smoke | `tests/live/test_sdk_smoke.py` | Skipped: opt-in not enabled; live acceptance remains open |

## Phase 9 verification record

Phase 9 is **VERIFIED on 2026-10-04** for deterministic status authority and
atomic transition auditing. The [testing record](TESTING.md#phase-9--verified-on-2026-10-04)
reports 59 passing PostgreSQL-backed pytest tests.

| Requirement IDs | Phase 9 test | Verified portion | Still pending |
|---|---|---|---|
| SW-13, SP-13 | Legal/illegal transition-table tests | Every state has explicit rules; required edges accepted and invalid edges rejected | Aggregate mixed-branch status and command/API surface |
| SW-28, SP-13, SP-33 | Stage-chain and workflow audit tests | Accepted state changes create ordered before/after audit events with actor/reason/version | Complete event coverage and metrics in Phase 21 |
| SP-13, SP-34 | Audit-failure and stale-version tests | Update/event atomic rollback, row lock and optimistic-version protection | Multi-process recovery and lease reconciliation |
| SW-37, SP-13 | Direct-mutation and agent-actor tests | ORM status writes outside `WorkflowOrchestrator` rejected; AGENT cannot be transition actor | Provider integration and bounded execution |
| SP-37 | Plan, testing and evidence record | Requested Phase 9 scope and limits recorded | Later phase records and end-to-end evidence |

No agent, gate, approval, scheduler or workflow HTTP endpoint executes through
this foundation yet.

## Phase 8 verification record

Phase 8 is **VERIFIED on 2026-10-04** for pure dependency readiness.
The [testing record](TESTING.md#phase-8--verified-on-2026-10-04) reports
44 passing pytest tests, including all three user-mandated cases.

| Requirement IDs | Phase 8 test | Verified portion | Still pending |
|---|---|---|---|
| SW-10, SW-16, SP-14 | `test_a_success_makes_b_ready` | Sequential `A → B` readiness after A succeeds | State transitions and gate enforcement |
| SW-17, SP-14 | `test_a_success_fans_out_to_b_and_c` | Both independent children become structurally ready | Actual concurrent execution in Phase 14 |
| SW-18, SP-14 | `test_join_waits_for_both_b_and_c` | Fan-in stays blocked until both predecessors succeed | Synchronization/candidate assembly in Phase 15 |
| SW-13, SP-13 | Wrong-generation, missing and non-success predecessor tests | Old or invalid evidence cannot release a child; resolver does not mutate state | Atomic state authority and restart recovery |
| SP-37 | Plan, testing and evidence record | Requested Phase 8 scope and limits recorded | Later phase records and final end-to-end evidence |

The resolver yields structural decisions only. It does not execute agents,
evaluate entry/exit gates, change stage records or claim concurrency.

## Phase 7 verification record

Phase 7 is **VERIFIED on 2026-10-04** for the requested YAML DAG and loader.
The [testing record](TESTING.md#phase-7--verified-on-2026-10-04) reports
32 passing pytest tests, including 14 graph tests.

| Requirement IDs | Phase 7 test | Verified portion | Still pending |
|---|---|---|---|
| SW-12, SW-14, SP-14 | `test_graph_validation.py::test_default_graph_has_required_fan_out_joins_and_approval_checkpoints` | Explicit 16-stage lifecycle and specified dependencies/joins | Persisted graph revision, actual resolver/execution and demonstration |
| SW-09, SP-14 | `test_graph_validation.py::test_blocking_ambiguity_inserts_clarification_without_cycle` | Conditional clarification graph variant without a same-generation cycle | Human answer, new analysis generation and blocking gate behavior |
| SW-14, SP-14 | Cycle/duplicate/unknown identifier/retry-policy tests | Invalid YAML and graph contracts rejected; safe symbolic registry | Executable bindings, timeout/schema contracts and workflow startup checks |
| SP-37 | Plan, testing record and ADR-002 | Requested Phase 7 scope and unimplemented execution boundary recorded | Later phase records and final end-to-end evidence |

The graph hash identifies loaded variants but is not yet stored as a
`graph_revisions` row or bound to a workflow. No agent, gate, stage or
approval was executed.

## Phase 6 verification record

Phase 6 is **VERIFIED on 2026-10-04** for the seven tables explicitly
requested. The [testing record](TESTING.md#phase-6--verified-on-2026-10-04)
records 18 passing pytest tests on disposable PostgreSQL, including all
Phase 5 regressions.

| Requirement IDs | Phase 6 test | Verified portion | Still pending |
|---|---|---|---|
| SW-19, SP-12 | `test_persistence.py::test_all_entities_round_trip_and_reload` | Durable workflow/scenario identity, exact input references and preserved stage attempts | DAG, state machine and execution in Phases 7–9 |
| SW-19, SW-20, SP-25 | `test_artifact_immutability.py`, `test_persistence.py` | Immutable versioned content/hash, requirement/component IDs, decisions and queryable lineage | Selective invalidation and full dependency lineage in Phases 18–19 |
| SW-21, SP-16 | `test_persistence.py::test_approval_foreign_key_binds_hash_and_version` | Approval request references exact artifact version/hash | Trusted reviewer decisions and invalidation in Phase 13 |
| SW-28, SP-33 | `test_persistence.py::test_audit_pages_remain_causal_under_concurrent_appends` | Append-only, per-workflow ordered and paginated audit events | Full transition/policy audit and metrics in Phases 9, 20–21 |
| SP-34 | `test_database.py`, `test_persistence.py` | Seven-table Alembic migration, UUID/FK/unique constraints, rollback and engine reload | Restart recovery, restricted runtime role and concurrency under later state transitions |
| SP-37 | Updated implementation/testing/traceability records | Requested Phase 6 scope and limitations recorded | Later phase records and final demonstration |

The earlier broad plan also named graph revisions, requirement versions,
policy events, clarifications and recovery incidents. Those records were not
requested in this seven-table implementation and remain open in their related
later phases. No workflow scheduling or agent-facing mutation API exists.

## Phase 5 verification record

Phase 5 is **VERIFIED on 2026-10-04** for the requested FastAPI bootstrap and
database scope. The [testing record](TESTING.md#phase-5--verified-on-2026-10-04)
records 9 passing pytest tests, including 4 against disposable PostgreSQL.

| Requirement IDs | Phase 5 test | Verified portion | Still pending |
|---|---|---|---|
| SP-01, SW-45 | `test_bootstrap.py`, Python build | Python 3.12 FastAPI service with separate package and migration ownership | Workflow runtime and complete deployment |
| SP-02 | Locked build, Ruff checks | SQLAlchemy 2 async extra, Alembic, psycopg, Pydantic settings, Typer, Rich and OpenAI Agents SDK installed from lock | SDK integration and security scanning in later phases |
| SP-11 | `test_health.py`, `test_bootstrap.py` | Database-backed 200/503 health, traceable error envelope, OpenAPI/docs | Workflow metrics and deployed readiness evidence |
| SP-34 | `test_database.py` | Clean Alembic baseline on PostgreSQL and transaction rollback | Workflow tables, restricted runtime DB role and concurrency/restart evidence |
| SP-37 | Updated plan and testing record | Authorized Phase 5 only; verification and limitations recorded | Per-phase records for Phases 6–28 |

The development Compose database currently uses a bootstrap administrator.
Least-privilege runtime role provisioning remains open for Phase 26. No
workflow model, agent behavior or scenario demonstration is claimed.

## Phase 4 verification record

Phase 4 was explicitly authorized and is **VERIFIED on 2026-10-04** in the actual repository. The [testing record](TESTING.md#phase-4--verified-on-2026-10-04) and [run manifest](evidence/phase-04-analytics/manifest.json) record the final `mvn verify` outcome: 37 tests, 0 failures, 0 errors and 0 skips, including real PostgreSQL Testcontainers analytics cases.

| Requirement IDs | Phase 4 test | Verified portion | Still pending |
|---|---|---|---|
| SW-03, SP-10 | `AnalyticsTest` | Successful redirect event fields, UTC daily aggregation, metadata/non-success non-counting, analytics `404` for missing code | Full assignment scenario and deployed-service evidence |
| SP-10 | `AnalyticsFailureIsolationTest`, `AnalyticsTimeoutTest`, `AnalyticsRecorderTest` | Forced write failure, stalled worker and PostgreSQL write timeout preserve `302`; queue rejection increments a dropped counter | Production retention policy, multi-instance durability and load testing |
| SP-11 | `ObservabilityTest` | Health/readiness, Prometheus, Micrometer counters, OpenAPI and restricted management exposure | Broader system observability in later orchestrator phases |
| SP-34 | `AnalyticsTest` and full Java suite | Flyway V3 and click-event persistence on real PostgreSQL | Orchestrator persistence, CI and live workflow evidence |
| SP-37 | Updated plan, traceability, testing, ADR and evidence | Authorized Phase 4 only; full test outcome and limits recorded | Per-phase records for Phases 5–28 |

The URL portion of E01 now has local automated evidence for core behavior, reliability and analytics. The complete assignment still needs agentic scenarios, deployment and final demonstration; local MockMvc/Testcontainers tests are not a deployed-service transcript.

## Phase 3 verification record

Phase 3 was explicitly authorized and is **VERIFIED on 2026-10-04** in the actual repository. The [testing record](TESTING.md#phase-3--verified-on-2026-10-04) and [run manifest](evidence/phase-03-reliability/manifest.json) record a complete `mvn verify` run: 29 tests, 0 failures, 0 errors and 0 skips. PostgreSQL Testcontainers exercises aliases, exact expiry, collision recovery, concurrent idempotency and disable behavior. The HTTP limiter is tested at both filter and API levels.

| Requirement IDs | Phase 3 test | Verified portion | Still pending |
|---|---|---|---|
| SW-04, SP-03 | `ExpiryTest`, `DisableLinkTest` | Expired/disabled redirects `410`; repeatable disable `204`; missing `404` | Analytics and complete assignment demonstration |
| SP-04 | `CollisionTest` | Forced generated collision then success, five-total-attempt exhaustion, healthy subsequent transaction | Further load/performance evidence in later phases |
| SP-05 | `AliasTest` | Format/length boundaries, reserved names, case-sensitive names, duplicate `409` | Brownfield scenario demonstration in Phase 24 |
| SP-06 | `ExpiryTest` | Future-only input and exact UTC boundary without cleanup job | Brownfield requirement-change demonstration |
| SP-07 | `IdempotencyTest` | Same response replay, changed request `409`, concurrent identical single creation/record | Authenticated caller scoping if added in a later phase |
| SP-09 | `RateLimitTest`, `RateLimitApiTest` | Bounded per-instance window, `429` and `Retry-After`; reset behavior documented | Multi-instance coordination is intentionally outside this phase |
| SP-34 | `LinkPersistenceTest` and Phase 3 PostgreSQL tests | Flyway V2, uniqueness and concurrent behavior on real PostgreSQL | Orchestrator/CI/live evidence |
| SP-37 | Updated plan, traceability, testing and evidence | Authorized Phase 3 only; full test outcome and limits recorded | Per-phase records for Phases 4–28 |

The Phase 3 portion of E01 is automated API and PostgreSQL test evidence. E01 remains incomplete until Phase 4 analytics evidence is recorded; no scenario, live agent or deployed-service transcript is claimed here.

## Phase 2 verification record

Phase 2 was explicitly authorized and is **VERIFIED on 2026-10-04** in the actual repository. [TESTING.md](TESTING.md#phase-2--verified-on-2026-10-04) and the [run manifest](evidence/phase-02-core/manifest.json) record `mvn test` and `mvn package`: both passed all 15 JUnit tests, including PostgreSQL Testcontainers integration tests, with no failures, errors or skips. The evidence bundle records the API assertions, Flyway V1 migration, uniqueness constraint and restart persistence. API assertions used MockMvc, not a separate deployed HTTP service.

| Requirement IDs | Phase 2 test | Verified portion | Still pending |
|---|---|---|---|
| SW-02, SP-03 | `LinkApiTest` | Create `201`, metadata lookup, valid redirect `302`, missing code `404` | Greenfield agentic generation/demo; disable and expired-link contracts in Phase 3 |
| SP-04 | `ShortCodeGeneratorTest`, `LinkPersistenceTest` | Secure seven-character Base62 generator and PostgreSQL unique constraint | Collision retry/exhaustion and concurrent handling in Phase 3 |
| SP-08 | `UrlValidationTest`, `LinkApiTest` | HTTP/HTTPS URL validation and invalid input rejection without fetching destination | Further parser/security hardening as later requirements demand |
| SP-11 | `LinkApiTest` | OpenAPI document, Actuator health, restricted `/actuator/env`, structured errors with trace ID | Readiness, metrics and broader observability in Phase 4 and orchestrator phases |
| SP-34 | `LinkPersistenceTest`, `LinkRestartTest` | Fresh Flyway V1 migration, constraint enforcement and data retained across app context restart on real PostgreSQL | Concurrent collision tests, Alembic/orchestrator persistence and later live evidence |
| SP-37 | Updated implementation plan, traceability and testing records | Authorized Phase 2 only, verified commands/results and explicit remaining work | Per-phase records for Phases 3–28 |

The Phase 2 portion of E01 is demonstrated by automated API and PostgreSQL test assertions; the complete E01 catalog entry still requires Phase 3 reliability and Phase 4 analytics evidence. No alias, expiry behavior, idempotency, rate limiting, analytics or agent orchestration is claimed.

## Phase 1 verification record

Phase 1 was explicitly authorized after planning and is **VERIFIED on 2026-10-04**. This section is the historical Phase 1 snapshot; Phase 2 progress appears above. The original three source documents are unchanged. The bootstrap files are installed in the repository. See [TESTING.md](TESTING.md#phase-1--verified-on-2026-10-04) and [the run manifest](evidence/phase-01-bootstrap/manifest.json) for actual commands, environment, sanitized transcripts and source hashes.

| Requirement IDs | Phase 1 evidence | Verified portion | Still pending |
|---|---|---|---|
| SP-01, SW-45 | `build-checks.txt`, `compose-lifecycle.txt` | Independent Java 21/Spring Boot and Python/FastAPI shells; separate database instances | Product/workflow functionality, Agents SDK, CLI and final packaging |
| SP-02 | `build-checks.txt`, `source-checks.txt`, `source-sha256.json` | Pinned build/format tooling, locked Python dependencies, digest-pinned PostgreSQL; exclusions for secrets/workspaces/caches | Later dependency additions and CI security scanning |
| SP-11 | Java `BootstrapTest` (2 passing), Python bootstrap tests (3 passing) | Framework startup and FastAPI OpenAPI/docs; business routes absent | Product APIs, custom health/readiness/metrics and structured business errors |
| SP-34 | `postgres-check.txt` | One real PostgreSQL fixture connectivity test passed | Flyway/Alembic, constraints/concurrency and all product/workflow integration tests |
| SP-35, SP-36, SW-42 | `compose-lifecycle.txt`, root README/Makefile | Database-only Compose starts, both DBs healthy, down preserves data; reproducible bootstrap commands | Application containers, migration startup, runner and full reviewer quick start |
| SP-37 | Updated Phase 1 record in implementation plan | Requested phase only; commands/results/status recorded | Each later phase requires separate implementation authorization |
| SW-40 | `decisions/ADR-001-service-boundaries.md` | Service ownership and bootstrap architecture decision | Implemented workflow/DAG/state/trust-boundary architecture |

All evidence filenames above are under `docs/evidence/phase-01-bootstrap/` unless another path is given. Python wheel/source distribution, Java executable JAR, structure, Compose syntax and lint checks all passed. The PostgreSQL test ran separately rather than being silently skipped. The disposable Docker resources were cleaned up. Known non-fatal dependency deprecation warnings are documented in TESTING.md. At Phase 1 completion, no business functionality, migrations, live model calls, scenarios, or CI were implemented or run; Phases 2–28 were then NOT_STARTED.
