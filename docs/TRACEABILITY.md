# Requirement Traceability Matrix

Baseline: 2026-10-04. Read with [IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md).

**Phases 1–4 are VERIFIED; Phases 5–28 remain PLANNED / NOT IMPLEMENTED / NOT TESTED / DEMONSTRATION PENDING.** The tables describe the complete scope. Actual Phase 1–4 evidence and partial coverage are recorded in the verification records below; the URL product alone does not complete agentic demonstrations or deployment requirements. No live SDK run, scenario, or performance result is claimed.

## Sources and notation

- Primary assignment: `docs/schwab-assignment.pdf`, three pages, read completely including page footers. Page/section references below identify the source requirement; requirement IDs are assigned by this plan for tracking, not printed IDs from Schwab.
- Implementation contract: `docs/IMPLEMENTATION_SPEC.md`, version 1.0, sections 1–20, read completely. Its details refine the assignment and are traced separately below so they are not misattributed to Schwab.
- Repository rules: `AGENTS.md`, read completely. Source paths/hashes and reconciliation notes appear in the implementation plan.
- `Pnn` identifies implementation phase nn. Test prefixes `JT/` and `OT/` expand exactly as defined in the plan. A suffix after `::` is a planned behavioral case, not an existing test result.
- Evidence IDs `E01`–`E16` refer to the catalog below. Each evidence bundle must include `docs/evidence/<run-id>/manifest.json`. Replace `<run-id>` with an actual recorded run; never create a success-looking placeholder.
- Each row's final evidence update must include commit, module, exact command/test selector, outcome, report link, demonstration link, provider mode and outstanding limitations. Shared test files are intentional; cases distinguish assertions.

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
| SW-08 | Well-defined and ambiguous requirements (p1 §3) | P13, P23, P25; clarification service | `OT/test_clarifications.py::blocks_until_answered`; `OT/scenarios/test_ambiguous.py::no_implementation_during_ambiguity` | E02 + E04: well-defined progress and visible clarification pause |
| SW-09 | Understand intent, identify ambiguity, normalize engineering problem (p1 §4.1) | P11–13, P25; RequirementAgent/schema | `OT/test_specialist_contracts.py::requirement_fields`; `OT/test_gates.py::unresolved_ambiguity_blocks` | E04: questions, assumptions, stable acceptance IDs and normalized version after human answer |
| SW-10 | Decompose into actionable dependent/sequenced tasks (p1 §4.2) | P7–8, P11; PlanningAgent, graph, resolver | `OT/test_specialist_contracts.py::task_dependencies`; `OT/test_dependency_resolver.py::sequential_and_fan_out` | E02–E04: task plan, impacted components and versioned dependency graph |
| SW-11 | Reason about actual brownfield modules/services/APIs/data flows (p1 §4.3) | P11, P24; search/read tools, architecture specialist | `OT/scenarios/test_brownfield.py::inspection_precedes_plan_and_maps_real_files` | E03: tool inspection receipts, impacted-file map, architecture/API/data-flow explanation |
| SW-12 | Coordinate complete SDLC: requirements, design, implementation, tests, docs, release readiness (p1 §4.4) | P7, P9, P11–15, P23; default graph and orchestrator | `OT/test_graph_validation.py::full_lifecycle_contract`; `OT/scenarios/test_greenfield.py::all_required_stages_complete` | E02 + E05: complete graph and causal execution timeline |
| SW-13 | Non-linear, stateful execution with governance (p1 §4.4) | P6–9, P13–16, P19; persistence/state machine | `OT/test_state_machine.py`; `OT/test_parallel_execution.py`; `OT/test_restart_recovery.py` | E05 + E10 + E12: concurrency, durable pause/restart and replan history |
| SW-14 | Explicit dependency graph (p1 §4.4) | P7; graph loader/config | `OT/test_graph_validation.py::reject_cycles_unknowns_duplicates` | E05: stored graph/hash, rejected invalid graph and displayed dependencies |
| SW-15 | Entry and exit gates (p1 §4.4) | P12; gate registry/evidence validation | `OT/test_gates.py::pass_fail_wait_and_current_evidence` | E06: missing/stale evidence blocks and genuine validated evidence passes |
| SW-16 | Sequential execution paths (p2 continuation §4.4) | P8–9; dependency resolver/state machine | `OT/test_dependency_resolver.py::a_before_b` | E05: B remains blocked until A succeeds |
| SW-17 | Parallel execution paths (p2 §4.4) | P14; scheduler/claims | `OT/test_parallel_execution.py::overlap_and_concurrency_cap`; `OT/test_stage_claims.py::single_active_claim` | E05: real overlapping start/end intervals and bounded active count |
| SW-18 | Synchronization of parallel paths (p2 §4.4) | P8, P15; joins/candidate assembly | `OT/test_synchronization_joins.py::delayed_parent_blocks_join`; `OT/test_candidate_assembly.py::conflicting_overlays` | E05: delayed branch blocks build/final-doc join; compatible candidate assembly manifest |
| SW-19 | Preserve cross-stage context (p2 §4.4) | P6, P10–11, P18; immutable inputs/provider context | `OT/test_lineage.py::exact_inputs_and_producer_attempts` | E10: exact requirement/design/candidate/evidence version chain |
| SW-20 | Preserve decision lineage (p2 §4.4) | P6, P18; decisions/lineage | `OT/test_lineage.py::decision_rationale_and_alternatives` | E10: decision tree with reasons, alternatives, actors and source artifacts |
| SW-21 | Human approvals for high-impact actions (p2 §4.4) | P13, P20; approvals/auth/policy | `OT/test_approvals.py::architecture_high_impact_assumption_release`; `OT/test_reviewer_auth.py::agent_cannot_approve` | E06 + E03: exact-version decisions before implementation/schema/API/security change and release |
| SW-22 | Bounded retries (p2 §4.4) | P16; retry policy/failure classifier | `OT/test_retry_policy.py::two_total_attempts_transient_only` | E07: attempt history, persisted delay, success after transient error and exhaustion stop |
| SW-23 | Fallback (p2 §4.4) | P16; fallback registry | `OT/test_fallback.py::configured_only_same_gates_with_provenance` | E07: labeled permitted fallback and unsupported-fallback safe-stop |
| SW-24 | Rollback (p2 §4.4) | P17; semantic compensation | `OT/test_compensation.py::restore_previous_approved_and_retain_failed`; `test_compensation_recovery.py::idempotent_restart` | E08: candidate rejected, previous approved reference restored, failed evidence retained |
| SW-25 | Safe-stop controls (p2 §4.4) | P14, P16–17; cancellation/recovery | `OT/test_safe_stop.py::no_descendants_late_results_fenced_human_resume` | E07–E08: persisted reason, last successful stage, action required and validated recovery |
| SW-26 | Security policy guardrails (p2 §4.4) | P11, P20; runner/tool policy/rules | `OT/test_runner_isolation.py`; `OT/test_guardrail_abuse.py::escape_secrets_commands_injection` | E09: denied attacks, runner restrictions and structured policy records |
| SW-27 | Compliance and change-control policy guardrails (p2 §4.4) | P13, P19–20; versioned policies/approvals/replan | `OT/test_policy_engine.py::versioned_rule_and_change_approval`; `OT/test_replanning.py::approval_invalidation` | E06 + E09 + E10: rule/version decisions and renewed approval on affected changes; scope explicitly local, no regulatory certification claimed |
| SW-28 | Audit-grade observability and traceability (p2 §4.4) | P6, P9, P18, P21; atomic audit/lineage | `OT/test_transition_atomicity.py`; `OT/test_audit_coverage.py::all_event_types_causal_order_redaction` | E11: sanitized causal audit with actors, versions, reasons and trace IDs; atomicity fault report |
| SW-29 | Success rate metric (p2 §4.4) | P21; metrics/reporting | `OT/test_metrics.py::success_rate_cohort_and_zero_denominator` | E11: completed/(completed+failed), declared window, cancelled/stopped counts and N/A |
| SW-30 | Retry frequency metric (p2 §4.4) | P16, P21 | `OT/test_metrics.py::retry_attempts_over_initial_attempts` | E11: raw counts and ratio reconciled with injected attempts |
| SW-31 | Rollback frequency metric (p2 §4.4) | P17, P21 | `OT/test_metrics.py::workflows_compensated_over_started_cohort` | E11: declared cohort, workflow count (not compensation-event count) and ratio |
| SW-32 | MTTR metric (p2 §4.4) | P16, P21 | `OT/test_metrics.py::resolved_incident_duration_unresolved_separate` | E11: controlled failure/recovery timestamps and unresolved incident count |
| SW-33 | End-to-end latency metric (p2 §4.4) | P21 | `OT/test_metrics.py::creation_to_completion_includes_human_wait` | E11: total plus execution/wait components with defined overlap accounting |
| SW-34 | Dynamic replanning on upstream changes while preserving governance (p2 §4.4) | P18–19, P25; impact/replan/generation fencing | `OT/test_replanning.py::expiry_change_selective_reuse`; `OT/test_replan_races.py::obsolete_result_rejected` | E04 + E10: 404→410 update, stale descendants/approvals, analytics reuse, renewed aggregate validation/release |
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
| SP-21 | Two total attempts; classified transient errors; no retry multiplication or uncertain-effect replay (spec §10.1) | P10, P16 | `OT/test_retry_policy.py` | E07 |
| SP-22 | Explicit fallback only, same gates/provenance, no manufactured validation/approval (spec §10.2) | P16 | `OT/test_fallback.py` | E07 |
| SP-23 | Semantic rollback preserves candidate/evidence; idempotent restore; no prior candidate and compensation-failure cases (spec §10.3) | P17 | `OT/test_compensation.py`, `test_compensation_recovery.py` | E08 |
| SP-24 | Safe-stop persists cause/last success/action; no descendants; authenticated validated recovery (spec §10.4) | P16 | `OT/test_safe_stop.py` | E07 |
| SP-25 | Immutable hashed artifacts, typed lineage relationships, decisions and exact inputs (spec §11.1; AGENTS) | P6, P18 | `OT/test_artifact_immutability.py`, `test_lineage.py` | E10 |
| SP-26 | Stable requirement/component selective impact; 404→410 example; reuse analytics; renew approvals and aggregate tests (spec §11.2) | P19, P25 | `OT/test_replanning.py`, `test_replan_races.py`, scenario ambiguous test | E04 + E10 |
| SP-27 | Versioned ALLOW/DENY/REQUIRE_APPROVAL policies; instruction injection untrusted; scanner severity/evidence (spec §12) | P11, P20 | `OT/test_policy_engine.py`, `test_guardrail_abuse.py` | E09 |
| SP-28 | Complete /api/v1 workflow APIs, fast return, invalid/stale rejection, pagination (spec §13.1) | P7, P9, P13, P16, P18–19, P21 | `OT/test_workflow_api.py`, `test_artifact_api.py`, API-specific tests | E06 + E10–E12 |
| SP-29 | All CLI commands, exact approval details, JSON/no-color/narrow display, watch interruption, explicit CI actors (spec §13.2) | P22–25 | `OT/test_cli.py`, `test_cli_api_contract.py`, scenario tests | E02–E04 CLI transcripts |
| SP-30 | Minimal greenfield seed; real generated files/tests/docs; separate live proof (spec §14.1) | P23 | `OT/scenarios/test_greenfield.py`, `OT/live/test_live_engineering_workflow.py` | E02 + E15 |
| SP-31 | Brownfield actual inspection and data-preserving alias/expiry upgrade (spec §14.2) | P24 | `OT/scenarios/test_brownfield.py` | E03 |
| SP-32 | Blocking ambiguity/questions/answers/versioning and failure-injection scenario variants (spec §14.3) | P13, P23–25 | Clarification and all scenario failure-variant tests | E04 + E07–E08 |
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
