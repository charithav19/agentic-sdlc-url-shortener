# Implementation Plan

Planning baseline: 2026-10-04. Current status: **Phases 1–8 VERIFIED for their requested scopes on 2026-10-04; Phases 9–28 NOT_STARTED**.

Execute only an explicitly requested phase after its prerequisites pass. The user authorized Phases 1–4; their actual implementation and verification are recorded below. Phases 5–28 remain proposed deliverables, not existing functionality or successful test results.

## Source review and reconciliation

Read completely from `/Users/raghavaveeragandham/Desktop/schwab-agentic-engineering`: `AGENTS.md`, all three pages of `docs/schwab-assignment.pdf` (text and rendered pages), and all 826 lines of `docs/IMPLEMENTATION_SPEC.md`. At the initial planning baseline, the repository contained only source/planning documents and no application implementation. Phase 1 bootstrap was subsequently installed and verified; the original source documents remain unchanged. This chat's starting directory is a separate projectless workspace.

| Source | SHA-256 |
|---|---|
| `AGENTS.md` | `bb9eba0447bafc3d315c41b4ca61a2f1a43aa2f50abf531f40a6ea54c5324006` |
| `docs/schwab-assignment.pdf` | `e6890463c402e67891cffdda9ffe2aef67880c43a1bd4a587657a62678411f42` |
| `docs/IMPLEMENTATION_SPEC.md` | `6939d38dcee8126fa08e564320357f971280e68d6026f8b4b41cea563d5e98ce` |

The assignment requires a working URL-shortening prototype and governed, non-linear SDLC automation. Its core requirement 4 is decomposed explicitly in [docs/TRACEABILITY.md](docs/TRACEABILITY.md). Technology choices, precise URL contracts, and detailed API/metric semantics come from the specification, not from the PDF. The specification's original caveat that the PDF was unavailable is resolved by this review; no source document is rewritten.

Reconciled constraints and qualifications:

- The PDF describes a 2–3 day assignment; the specification expressly retains the full scope. Preserve all 28 phases and report schedule risk rather than silently reducing scope or promising completion within that window.
- The PDF calls for production-quality engineering. Demonstrate tested quality, defensible boundaries, and safe change management; do not equate a local prototype with production certification.
- The PDF is marked `Schwab Internal`. Keep it local; this plan does not authorize public publication of the PDF or repository. Reconfirm permitted distribution before a future public submission.
- The specification's final expired-link contract is `410`. The earlier `404` behavior is confined to the requirement-change demonstration and must not become the final product behavior.
- The assignment's tools/examples do not override the chosen Java/Spring Boot, FastAPI, OpenAI Agents SDK, PostgreSQL, Typer/Rich, and Docker Compose architecture.
- No Kafka, Redis, Kubernetes, Temporal, LangGraph, React, Angular, MongoDB, or Elasticsearch. No application code, migrations, configuration, or seeds are created by this planning task.

## Execution conventions

Paths are repository-relative. The following exact prefixes make the per-phase file lists readable; append the listed suffix literally:

| Prefix | Exact repository path |
|---|---|
| `J/` | `apps/url-shortener/src/main/java/com/schwab/urlshortener/` |
| `JT/` | `apps/url-shortener/src/test/java/com/schwab/urlshortener/` |
| `JR/` | `apps/url-shortener/src/main/resources/` |
| `O/` | `apps/orchestrator/app/` |
| `OT/` | `apps/orchestrator/tests/` |
| `M/` | `apps/orchestrator/alembic/versions/` |

The Java package is a planning choice, not a claim about existing code. File lists include new and modified files. Package `__init__.py` files follow the listed Python package boundaries. Java integration tests retain the required `*Test.java` naming and are tagged/configured so Maven verification actually executes PostgreSQL tests. Python integration tests use a real PostgreSQL fixture, never SQLite as a concurrency substitute.

Every phase must update this plan's status and `docs/TRACEABILITY.md` with commands, actual outcomes, remaining failures, and evidence references. Status vocabulary: `NOT_STARTED`, `IN_PROGRESS`, `BLOCKED` (with reason), `VERIFIED` (with evidence). Completion requires tests plus phase acceptance criteria; a document or fake-provider transcript alone does not prove a live engineering capability.

Evidence convention: `docs/evidence/<run-id>/manifest.json` records commit, environment/tool versions, provider mode/model/SDK, source/graph/candidate hashes, commands, timestamps, outcomes, artifact references, and sanitization. Store sanitized reports/transcripts beside it. Never fabricate these files before a run. Ordinary CI uses the fake provider and explicit fixture human approvals; live smoke and a live engineering workflow are separate required evidence.

## Dependency order and foundations

Execute phases numerically. The direct dependency table records technical prerequisites; earlier phases remain reviewed milestones even when not technical prerequisites. Every dependency points backward.

| Phase | Direct prerequisites |
|---|---|
| 1 | Source review and this plan |
| 2 | 1 |
| 3 | 2 |
| 4 | 3 |
| 5 | 1 |
| 6 | 5 |
| 7 | 6 |
| 8 | 7 |
| 9 | 6, 8 |
| 10 | 5, 9 |
| 11 | 7, 10 |
| 12 | 8, 9, 11 |
| 13 | 6, 9, 12 |
| 14 | 9, 11, 12, 13 |
| 15 | 8, 12, 14 |
| 16 | 9, 10, 14, 15 |
| 17 | 6, 13, 15, 16 |
| 18 | 6, 13, 17 |
| 19 | 7, 9, 13, 16, 18 |
| 20 | 11, 12, 13, 16, 19 |
| 21 | 9, 16, 17, 19, 20 |
| 22 | 13, 18, 19, 21 |
| 23 | 4, 15, 17, 20, 22 |
| 24 | 3, 23 |
| 25 | 19, 23, 24 |
| 26 | 4, 5, 11, 22, 23, 24, 25 |
| 27 | 26 |
| 28 | 27 and all prior acceptance gates |

Resolve potential forward dependencies as follows:

- Phase 6 introduces immutable artifact identity, exact inputs, requirement/component IDs, approval records, and append-only audit storage. Phase 18 completes lineage services and queries; it does not retrofit missing provenance.
- Phase 9 commits transitions and audit atomically. Phase 21 completes event coverage and metrics, not basic audit correctness.
- Phase 7 validates symbolic executor/gate contracts with registries. Concrete implementations arrive in Phases 11–12; workflows are not executable until their required registrations exist.
- Phase 8 computes readiness without changing state. Phase 9 is the sole state writer. Phase 14 adds scheduling; Phase 15 adds production candidate joins. Before Phase 15, scheduler verification uses harmless stage fixtures and isolated outputs, not an incomplete engineering pipeline.
- Phase 11 implements mandatory tool restrictions and a restricted runner immediately. Phase 20 completes unified governance and adversarial coverage. Live candidate execution is disabled until isolation passes; no temporary unrestricted shell tool is acceptable.
- Phase 13 implements clarification persistence/API and baseline requirement regeneration so the Phase 22 CLI is complete; Phase 19 extends this to arbitrary upstream changes and selective replanning. Phase 25 demonstrates the capability rather than implementing it late.
- Phase 14 includes claim tokens, cancellation, and basic generation fencing; Phase 16 completes safe-stop/recovery and retry semantics. Phase 17 uses Phase 6 immutable references to compensate; Phase 18 extends queryability.
- PostgreSQL test fixtures and the trusted candidate runner arrive before Phase 26. Phase 26 packages the complete Compose stack; early tests and scenario runs use the already verified local/test infrastructure.

## PHASE 1 — Repository/bootstrap

**Objective:** Establish reproducible service boundaries, build tooling, formatting, and test infrastructure without claiming any product behavior.

**Exact modules/files expected:** `.gitignore`, `.editorconfig`, `.env.example`, `README.md`, `Makefile`, `apps/url-shortener/pom.xml`, `apps/url-shortener/mvnw`, `apps/url-shortener/mvnw.cmd`, `apps/url-shortener/.mvn/wrapper/maven-wrapper.properties`, `J/UrlShortenerApplication.java`, `JR/application.yml`, `JT/BootstrapTest.java`, `apps/orchestrator/pyproject.toml`, `apps/orchestrator/uv.lock`, `O/__init__.py`, `OT/conftest.py`, `OT/test_bootstrap.py`, `workspaces/.gitkeep`, `docs/decisions/ADR-001-service-boundaries.md`, `docs/TESTING.md`.

**Data model changes:** None; document separate service-owned PostgreSQL databases/roles and migration ownership. Pin Java 21, Python 3.12+, compatible dependencies, formatting/lint tools, and test database image during implementation.

**APIs:** No business API. Define configuration names and future Make targets; only implemented targets may be advertised as working.

**Dependencies:** Source review and this plan. Confirm Docker, Java, Python, and package-download prerequisites.

**Tests:** `JT/BootstrapTest.java`, `OT/test_bootstrap.py`; wrapper execution, package import, formatting checks, locked dependency installation, and PostgreSQL fixture connectivity.

**Acceptance criteria:** Both skeletons build/import from documented commands; versions are pinned; secrets and generated workspaces are ignored; service owners and configuration are documented; no prohibited infrastructure.

**Risks:** Dependency incompatibility, wrapper downloads, Docker availability, and accidental secret tracking. Resolve versions here rather than guessing them in the plan.

**Status:** VERIFIED — completed 2026-10-04. The bootstrap is installed in the actual repository, not only in the staging workspace. No business functionality was implemented during Phase 1; its record is a point-in-time snapshot.

**Implementation record:** Added the required `apps/url-shortener`, `apps/orchestrator`, `docs`, `scenarios`, `workspaces` and `scripts` layout; root README, Makefile, `.env.example`, `.gitignore`, `.editorconfig`; pinned Maven Wrapper and Spring Boot/Python build configurations; minimal Java entry point and empty FastAPI ASGI app; bootstrap tests; database fixture and structure-check scripts; service-boundary ADR; testing documentation and evidence. `docker-compose.yml` is a database-only skeleton explicitly requested for Phase 1, with isolated databases/roles/volumes and a digest-pinned PostgreSQL image. Scenario and Alembic directories contain placeholders only. `O/main.py` is introduced as an empty application shell here; Phase 5 still owns configuration, health, sessions and migrations.

**Pinned baseline:** Java 21; Spring Boot 3.5.16; Maven 3.9.16 / wrapper 3.3.4 with distribution checksum; Python 3.12.13 / uv 0.11.8; exact Python dependency pins and `uv.lock`; Spotless 3.10.3 / Google Java Format 1.28.0 AOSP; Ruff 0.16.10. Database image: PostgreSQL 17.7 Alpine with recorded SHA-256 digest. No schema or application database layer exists yet.

**Verification:** `make bootstrap structure compose-config lint build test-python` passed from the actual repository. Maven verification built the executable JAR with 2 tests passing; the Python wheel/source distribution built, and 3 FastAPI bootstrap tests passed. `make test-db` passed 1 real PostgreSQL connectivity test. An isolated Compose run verified `make up`, both database health checks, and `make down` preserving named volumes; only its disposable test resources were then removed. Git-ignore rules, wheel contents, explicit rejection of deferred demo/smoke commands, and original source hashes were verified. No Git commit or publication was performed.

**Evidence:** [Phase 1 verification](docs/TESTING.md), [run manifest](docs/evidence/phase-01-bootstrap/manifest.json), [traceability progress](docs/TRACEABILITY.md#phase-1-verification-record). Commands, environment, actual outcomes, sanitized logs and source hashes are recorded there.

**Remaining limitations:** Mockito dynamic-agent and Starlette HTTPX compatibility deprecation warnings are documented and unsuppressed; all Phase 1 tests pass. Compose includes development database administrators only, not later restricted application roles or the final application stack. Database persistence features, health APIs, agent runtime, scenarios, CI and all product behavior remain in later phases.

## PHASE 2 — Spring Boot URL shortener core

**Objective:** Persist validated URLs, return short-link metadata, and redirect active links.

**Exact modules/files expected:** `J/api/LinkController.java`, `J/api/RedirectController.java`, `J/api/CreateLinkRequest.java`, `J/api/LinkResponse.java`, `J/api/ApiExceptionHandler.java`, `J/api/ApiError.java`, `J/application/LinkService.java`, `J/application/RedirectService.java`, `J/domain/Link.java`, `J/domain/LinkStatus.java`, `J/domain/ShortCodeGenerator.java`, `J/domain/SecureShortCodeGenerator.java`, `J/domain/UrlValidator.java`, `J/persistence/LinkRepository.java`, `J/config/ClockConfig.java`, `J/config/ShortUrlProperties.java`, `J/observability/TraceIdFilter.java`, `J/analytics/package-info.java`, `JR/db/migration/V1__create_links.sql`, `JT/LinkApiTest.java`, `JT/UrlValidationTest.java`, `JT/LinkPersistenceTest.java`, `JT/LinkRestartTest.java`, `JT/LinkServiceTest.java`, `JT/ShortCodeGeneratorTest.java`; modify `apps/url-shortener/pom.xml`, `J/UrlShortenerApplication.java`, `JR/application.yml`, root `README.md`, and `Makefile`; add `J/application/LinkNotFoundException.java`, `J/domain/InvalidUrlException.java`.

**Data model changes:** `links`: UUID, unique case-sensitive `short_code`, original URL, active/disabled status, UTC creation time, nullable expiry reserved for Phase 3, optimistic version. Seven-character secure Base62 generation; database uniqueness is mandatory from the first insert.

**APIs:** `POST /api/v1/links` → `201`; `GET /{shortCode}` → `302` with `Location` or `404`; `GET /api/v1/links/{shortCode}` → metadata or `404`. Metadata fields match specification §4.1. Stable structured errors include code, message, trace ID, and validation details.

**Dependencies:** Phase 1.

**Tests:** Creation/lookup/redirect round trip; restart persistence; missing code; absolute HTTP/HTTPS with host; malformed URL, credentials, control characters, unsupported scheme rejection; no destination fetch; fresh Flyway migration on PostgreSQL.

**Acceptance criteria:** Core API and persistence tests pass; no read-before-insert uniqueness guarantee; metadata does not count clicks; failures do not expose stack traces/secrets.

**Risks:** URL parser edge cases, catch-all redirect routing intercepting management paths, and treating random generation as a uniqueness guarantee.

**Status:** VERIFIED — completed 2026-10-04 in the actual repository. The remaining Phase 3 work described below was implemented subsequently; this Phase 2 record is historical.

**Implementation record:** Java 21/Spring Boot 3.5.16 Maven service now persists validated HTTP(S) links through JPA/PostgreSQL and Flyway V1, creates cryptographically random seven-character Base62 codes, returns metadata, and redirects valid codes with `302`. The migration enforces a unique `short_code`; collision recovery is deferred to Phase 3. Structured `400`/`404` errors include a trace ID. Only Actuator health/info are exposed, and `/v3/api-docs` is available. `analytics/` is a package placeholder with no analytics behavior. Alias, expiry behavior, idempotency, rate limiting, disable handling, and collision retry remain unimplemented.

**Verification:** From `apps/url-shortener` in the actual repository, `mvn test` and `mvn package` both passed with Java 21 and Maven 3.9.16; each executed 15 tests with 0 failures, 0 errors, and 0 skips. PostgreSQL Testcontainers tests verified the fresh Flyway migration, database uniqueness, API contracts, and link availability after closing and reopening the Spring application context against the same database. `mvn package` built the executable JAR. See [Phase 2 testing record](docs/TESTING.md#phase-2--verified-on-2026-10-04), [run manifest](docs/evidence/phase-02-core/manifest.json), and [traceability progress](docs/TRACEABILITY.md#phase-2-verification-record).

## PHASE 3 — URL reliability: aliases, expiry, collision handling, idempotency, rate limiting

**Objective:** Make creation/redirect behavior deterministic at boundaries and under concurrent requests; add soft disable.

**Exact modules/files expected:** Modify Phase 2 API/domain/service files, `J/UrlShortenerApplication.java`, `J/observability/TraceIdFilter.java`, `JR/application.yml`, root `README.md` and `.env.example`; add `J/domain/AliasValidator.java`, `J/domain/InvalidAliasException.java`, `J/application/CollisionRetryExecutor.java`, `J/application/CollisionExhaustedException.java`, `J/application/IdempotencyService.java`, `J/application/InvalidIdempotencyKeyException.java`, `J/application/InvalidExpiryException.java`, `J/application/LinkConflictException.java`, `J/application/LinkGoneException.java`, `J/persistence/IdempotencyRecord.java`, `J/persistence/IdempotencyRepository.java`, `J/config/CreationRateLimitFilter.java`, `J/config/RateLimitProperties.java`, `JR/db/migration/V2__add_idempotency.sql`, `JT/AliasTest.java`, `JT/ExpiryTest.java`, `JT/CollisionTest.java`, `JT/IdempotencyTest.java`, `JT/RateLimitTest.java`, `JT/RateLimitApiTest.java`, `JT/DisableLinkTest.java`, `JT/MutableClock.java`, `JT/UrlIntegrationTestSupport.java`, and `apps/url-shortener/src/test/resources/mockito-extensions/org.mockito.plugins.MockMaker`.

**Data model changes:** `idempotency_records`: caller scope, key, canonical request fingerprint, original response and link reference, creation time; unique `(caller_scope,key)`. One-way disable conditionally updates active rows and advances the link version, so concurrent repeated disables are safe. Retain keys throughout the demo retry window; initial policy is no automatic eviction from durable idempotency storage, documented for later retention work. Limiter state is bounded and in memory only.

**APIs:** Create accepts `customAlias`, `expiresAt`, `Idempotency-Key`; alias conflict or mismatched replay → `409`; invalid alias/expiry → `400`; throttle → `429` plus `Retry-After`; expired/disabled redirect → `410`. `DELETE /api/v1/links/{shortCode}` → repeatable `204`, missing → `404`. Identical replay returns the original creation result.

**Dependencies:** Phase 2.

**Tests:** Alias length 3/32 boundaries, regex, case-sensitive uniqueness and case-insensitive reserved names (`api`, `actuator`, `swagger-ui`, `v3`, `health`); expiry strictly future and exact UTC boundary; forced collisions then success and five-total-attempt exhaustion with transaction recovery; same/different/concurrent idempotency payloads; limiter window/capacity/eviction; repeated disable and concurrent mutations. Execute concurrency tests against PostgreSQL.

**Acceptance criteria:** Concurrent identical requests create one link; collision retries use recoverable transactions/savepoints and stop after five total attempts; alias conflicts are not retried as generated collisions; no expiry cleanup job dependency; limiter memory is bounded and per-instance/restart limits documented.

**Risks:** Aborted PostgreSQL transactions after unique violations, ambiguous fingerprint normalization, shared anonymous caller keys, reserved-route conflicts, and clock boundary errors. Document anonymous caller scope; the global limiter deliberately does not rely on client IP or proxy headers.

**Status:** VERIFIED — completed 2026-10-04 in the actual repository. This Phase 3 record is historical; Phase 4 was implemented subsequently.

**Implementation record:** Flyway V2 widens `links.short_code` for aliases while retaining the unique constraint and adds durable `idempotency_records` with a unique `(caller_scope, request_key)` key and stored original response. Alias validation enforces the stated length, alphabet, reserved words and case sensitivity. An injectable generator supplies random codes; collision handling uses PostgreSQL `INSERT ... ON CONFLICT DO NOTHING` inside the creation transaction, so failed attempts do not abort it, and stops after five total attempts. Expiry uses the injected UTC clock; soft disable uses an atomic status update that increments the version. Transaction-scoped PostgreSQL advisory locks serialize requests sharing an idempotency key, including concurrent requests across instances. The creation limiter is a bounded single-window, per-instance in-memory filter; it returns structured `429` with `Retry-After`. The scope is currently `anonymous` because authentication has not been added; keys are retained indefinitely, and the limiter resets on restart. No Redis or Phase 4 analytics was added.

**Verification:** From `apps/url-shortener`, `mvn test` passed after the initial implementation (28 tests). After adding the HTTP limiter and Flyway V2 assertions, `mvn verify` passed with 29 tests, 0 failures, 0 errors and 0 skips, including real PostgreSQL Testcontainers cases for aliases, exact expiry, collision recovery/exhaustion, concurrent idempotency and disable. The executable JAR was built. See [Phase 3 testing record](docs/TESTING.md#phase-3--verified-on-2026-10-04), [run manifest](docs/evidence/phase-03-reliability/manifest.json), and [traceability progress](docs/TRACEABILITY.md#phase-3-verification-record).

## PHASE 4 — URL analytics and observability

**Objective:** Count successful redirects with best-effort analytics that cannot break valid redirects; expose operational evidence.

**Exact modules/files expected:** `J/analytics/ClickEvent.java`, `J/analytics/ClickEventRepository.java`, `J/analytics/AnalyticsRecorder.java`, `J/analytics/AnalyticsWriter.java`, `J/analytics/AnalyticsService.java`, `J/api/AnalyticsController.java`, `J/api/AnalyticsResponse.java`, existing `J/observability/TraceIdFilter.java`, `J/observability/UrlMetrics.java`, `J/config/AnalyticsProperties.java`, `J/config/ManagementConfig.java`, `JR/db/migration/V3__create_click_events.sql`, `JT/AnalyticsTest.java`, `JT/AnalyticsFailureIsolationTest.java`, `JT/AnalyticsTimeoutTest.java`, `JT/AnalyticsRecorderTest.java`, `JT/ObservabilityTest.java`, `docs/decisions/ADR-005-analytics-design.md`; modify `RedirectService`, `RedirectController`, `UrlShortenerApplication`, `application.yml`, `pom.xml`, `.env.example`, root `README.md`, and the existing Java integration tests/support to isolate their Phase 2–3 expectations.

**Data model changes:** `click_events`: link FK, UTC timestamp, sanitized optional referrer, coarse user-agent category, trace ID; index `(link_id,occurred_at)`. No raw client IP by default.

**APIs:** `GET /api/v1/links/{shortCode}/analytics` → code, total clicks, UTC daily counts or `404`; Actuator health/readiness/Prometheus and OpenAPI endpoints. Restrict sensitive management endpoints.

**Dependencies:** Phase 3.

**Tests:** UTC date aggregation, metadata/non-success non-counting, sanitized fields, forced write exception and timeout both preserve `302`, bounded analytics resources, failure counter and trace propagation, management exposure checks.

**Acceptance criteria:** Analytics uses an independent transaction and bounded execution/queue/time budget; failure never changes a valid redirect; lost events and best-effort semantics documented; no exactly-once claim.

**Risks:** Hidden synchronous blocking, pool exhaustion, cardinality growth, and leaking destination queries/referrers. Set explicit retention and redaction configuration.

**Status:** VERIFIED — completed 2026-10-04 in the actual repository. Phases 5–28 remain NOT_STARTED.

**Implementation record:** Flyway V3 adds `click_events` with a link foreign key and `(link_id, occurred_at)` index. Valid redirects submit an event containing link ID, UTC timestamp, origin-only HTTP(S) referrer, coarse user-agent category and trace ID. Raw IP, raw user-agent, referrer path and query are not stored. A bounded two-thread/100-item executor writes events in independent `REQUIRES_NEW` transactions with two-second transaction and PostgreSQL statement timeouts; connection acquisition defaults to three seconds. Queue rejection and writer exceptions increment separate Micrometer counters and do not alter a valid `302`. Analytics totals are computed from persisted events in a single UTC-day aggregation query, so recent redirects may not yet appear. Actuator health/readiness, metrics and Prometheus are exposed; sensitive management routes remain closed. Events have no automatic deletion; best-effort delivery and this retention policy are documented in [ADR-005](docs/decisions/ADR-005-analytics-design.md).

**Verification:** From `apps/url-shortener`, the final `mvn verify` run passed 37 JUnit tests with 0 failures, 0 errors and 0 skips and built the executable JAR. Real PostgreSQL Testcontainers tests cover UTC aggregation, persisted event fields, non-success and metadata non-counting, forced writer failure, an actual PostgreSQL write timeout and a stalled writer preserving `302`, management endpoints and metrics. A unit test forces queue rejection and checks the dropped-event counter. See [Phase 4 testing record](docs/TESTING.md#phase-4--verified-on-2026-10-04), [run manifest](docs/evidence/phase-04-analytics/manifest.json), and [traceability progress](docs/TRACEABILITY.md#phase-4-verification-record).

## PHASE 5 — FastAPI orchestrator bootstrap and database

**Objective:** Establish typed configuration, health, database sessions, migrations, and test lifecycle.

**Exact modules/files expected:** `O/main.py`, `O/config.py`, `O/api/health.py`, `O/api/errors.py`, `O/api/dependencies.py`, `O/persistence/base.py`, `O/persistence/session.py`, `apps/orchestrator/alembic.ini`, `apps/orchestrator/alembic/env.py`, `M/0001_database_baseline.py`, `OT/test_health.py`, `OT/test_database.py`; extend `OT/conftest.py`.

**Data model changes:** Orchestrator schema/migration baseline and separate least-privilege role; no URL tables accessible to orchestrator role. UTC/UUID conventions and unit-of-work rollback behavior.

**APIs:** Root `GET /health`, `/docs`, `/openapi.json`; structured error envelope and request trace ID. Health indicates database readiness without leaking credentials.

**Dependencies:** Phase 1; PostgreSQL test infrastructure is available before final Compose packaging.

**Tests:** Healthy/unavailable database, session cleanup and rollback, isolated credentials, clean migration upgrade, import/config failures for invalid settings.

**Acceptance criteria:** Service starts with validated config; health reflects real readiness; tests use PostgreSQL and independent transactions; secrets never appear in errors.

**Risks:** Async session misuse and migration startup races. Select one explicit migration owner/process.

**Status:** VERIFIED on 2026-10-04 for the requested Phase 5 service scope. Nine Python tests passed (five local, four against disposable PostgreSQL), Ruff lint/format passed, and the wheel/sdist built. The Alembic baseline creates only its version table; no workflow model or route exists. Development Compose still provisions its orchestrator user as a PostgreSQL bootstrap administrator; restricted runtime role provisioning remains for Phase 26 and is not claimed as complete here.

**Implementation record:** Added the requested package boundaries, typed environment settings, a PostgreSQL async engine and transaction-scoped sessions, explicit Alembic migration ownership, JSON request logs and trace IDs, a database-backed `GET /health`, structured errors, and FastAPI OpenAPI/docs. Locked SQLAlchemy 2 with its async extra, Alembic, psycopg, pydantic-settings, openai-agents, Typer and Rich. Startup initializes the connection pool but does not migrate or connect until a probe/use; operators run `alembic upgrade head` separately. The initial migration has no workflow tables.

**Verification:** `uv run --locked python -m pytest -m 'not integration' -q` passed 5 tests. `scripts/test-postgres.sh -q` passed 4 integration tests using disposable PostgreSQL. Ruff lint and format checks passed; `uv build --no-sources` built a wheel and sdist. Healthy `/health` returned 200 and unavailable database 503 without credential disclosure. The migration applied cleanly and sessions demonstrated commit/rollback.

## PHASE 6 — Workflow persistence model

**Objective:** Persist the complete execution identity and minimum governance/provenance foundation before scheduling exists.

**Exact modules/files expected:** `O/persistence/models.py`, `O/persistence/repositories.py`, `O/persistence/unit_of_work.py`, `O/orchestration/contracts.py`, `O/artifacts/store.py`, `O/artifacts/schemas.py`, `O/observability/audit_store.py`, `M/0002_workflow_foundation.py`, `OT/test_persistence.py`, `OT/test_artifact_immutability.py`.

**Data model changes:** `workflow_runs`, `stage_runs`, `graph_revisions`, `requirement_versions`, `artifacts`, `artifact_lineage`, `decisions`, `approvals`, `audit_events`, `policy_events`, `clarifications`, `recovery_incidents`. Include scenario/provider, generation/attempt, exact input IDs/hashes, graph hash, version counters, lease/token fields, retry due time, stop/last-success details. Unique stage attempt identity `(workflow_id,generation,stage_name,attempt)`. Artifacts retain immutable content/hash/schema/producer/input references and stable requirement/component IDs; lifecycle events do not rewrite content. Approvals reference exact artifact/hash and trusted actor. Audit uses durable per-workflow causal sequence. Persist candidate/current-approved references without selecting an unapproved candidate as approved.

**APIs:** Internal repository, immutable artifact-store, and unit-of-work interfaces only. No general state-update API for agents or clients.

**Dependencies:** Phase 5.

**Tests:** PostgreSQL round trips for every entity, FKs/unique constraints, atomic rollback, attempt preservation, hash integrity, immutable content rejection, paginated audit ordering, full reload after process restart.

**Acceptance criteria:** Every later stage can reference exact inputs from inception; no overwritten attempts; no direct state mutations outside the future orchestrator; baseline migration applies to a fresh database.

**Risks:** Monolithic requirement lineage preventing selective reuse, mutable blob locations, and JSON-only unqueryable governance history. Use stable requirement/component identifiers and verifiable durable content.

**Status:** VERIFIED on 2026-10-04 for the seven-table Phase 6 scope explicitly requested. A complete pytest run passed 18 tests against disposable PostgreSQL, including all earlier FastAPI tests. Workflow scheduling and status transitions are not implemented.

**Implementation record:** Added the exact ScenarioType, WorkflowStatus and StageStatus vocabularies; UUID-keyed workflow runs, stage attempts, immutable/versioned artifacts, lineage, decisions, exact-version/hash approvals and append-only audit events. PostgreSQL constraints enforce stage-attempt identity, cross-workflow lineage isolation, approval exact references and per-workflow audit sequence uniqueness. Database triggers reject artifact/audit update, delete and truncate. Internal repositories, unit-of-work, artifact store, audit store and creation service commit provenance with its audit event atomically. Alembic revision `0002_workflow_foundation` applies after the Phase 5 baseline. No API or agent-facing state mutation was added.

**Verification:** Full `python -m pytest --require-postgres -q` on disposable PostgreSQL 17.7 passed 18 tests, 0 failures/skips. Tests cover fresh migration, all seven entity round trips and engine reload, stage uniqueness, foreign keys, exact input/approval references, transaction rollback, immutable contents and audit history, concurrent artifact version assignment and causal audit pagination. Ruff lint/format checks passed.

**Scope boundary:** The earlier broad Phase 6 plan also listed `graph_revisions`, `requirement_versions`, `policy_events`, `clarifications` and `recovery_incidents`. The user requested only seven tables here, so those companion records remain for their related later phases. Graph revision fields are stored as UUID/hash references without a graph table yet. Approval decisions, stage transitions, scheduling, agent execution and runtime role provisioning remain outside this phase.

## PHASE 7 — Explicit configurable DAG

**Objective:** Parse and version an explicit SDLC graph with validated stage contracts.

**Exact modules/files expected:** `apps/orchestrator/config/default_sdlc.yaml`, `O/orchestration/graph.py`, `O/orchestration/graph_loader.py`, `O/orchestration/registry.py`, `O/api/graphs.py`, `OT/test_graph_validation.py`, `docs/decisions/ADR-002-deterministic-orchestration.md`.

**Data model changes:** Persist immutable graph content/hash/version in `graph_revisions`; bind workflows to that version. Stage contracts include dependencies, executor, entry/exit gates, retry/fallback/approval policy, timeout, input/output schema IDs.

**APIs:** `GET /api/v1/workflows/{id}/graph`; internal `load_graph` and `validate_graph`. Configuration resolves registered identifiers only and never imports arbitrary code.

**Dependencies:** Phase 6. Registry contract declarations precede concrete executors/gates.

**Tests:** Cycles, duplicate names, missing dependencies, unknown executor/gate/schema, invalid attempts/timeouts/fallback, deterministic hash, and approved optional-stage semantics.

**Acceptance criteria:** Graph explicitly represents intake → analysis → decomposition → architecture → approval; parallel implementation/test design/documentation; build join; parallel unit/integration/security; documentation join; release readiness/approval/completion. Clarification creates a new graph/generation rather than a back edge. Incomplete executable registrations block workflow execution.

**Risks:** Treating a diagram as execution configuration or creating cycles through clarification. Distinguish graph generations from within-generation edges.

**Status:** VERIFIED on 2026-10-04 for the requested configurable-DAG scope. The full Python suite passed 32 tests against disposable PostgreSQL, including 14 new graph tests; Ruff checks and wheel/sdist build passed. No agent or stage was executed.

**Implementation record:** Added `config/default_sdlc.yaml` with 16 ordinary stages, the specified fan-out/fan-in joins, two approval checkpoints and a conditional `CLARIFICATION` insertion. Every stage declares name, dependencies, executor, entry/exit gates, retry policy, fallback and approval requirement. The safe YAML loader rejects duplicate keys and unknown identifiers, validates both graph variants, detects cycles and produces a deterministic SHA-256/version. The YAML is packaged in the wheel. [ADR-002](docs/decisions/ADR-002-deterministic-orchestration.md) records the graph-generation choice.

**Scope boundary:** The user requested the graph configuration, loader and validation in this phase. Planned `graph_revisions` persistence, workflow binding, graph HTTP API, timeout/schema contracts and executable registry bindings remain for later orchestration phases. Clarification does not add a same-generation back edge; re-analysis after a human answer requires a new generation in later phases.

## PHASE 8 — Dependency resolver + fan-out/fan-in

**Objective:** Compute structurally eligible stages with pure, deterministic dependency resolution.

**Exact modules/files expected:** `O/orchestration/dependencies.py`, `O/orchestration/readiness.py`, `OT/test_dependency_resolver.py`.

**Data model changes:** None; consume persisted graph/generation/status/input references. Return readiness/block reasons without mutating stage state.

**APIs:** Internal resolver returning eligible/blocked stage IDs and unmet dependencies. Gate evaluation and execution are composed later.

**Dependencies:** Phase 7.

**Tests:** `A→B`; `A→B,C`; `B,C→D`; delayed, failed, stale, rolled-back, wrong-generation and missing parents; optional skip accepted only by explicit graph policy; deterministic repeated resolution.

**Acceptance criteria:** Both fan-out children become eligible after A succeeds; D remains blocked until B and C both succeed for the applicable generation; no resolver write or implicit execution.

**Risks:** Confusing structural eligibility with permission to execute. The final scheduler must additionally check gates, approvals, policy, and claims.

**Status:** VERIFIED on 2026-10-04 for the requested Phase 8 resolver scope. The full orchestrator pytest suite passed 44 tests, including the three mandatory sequential, fan-out and fan-in cases, against disposable PostgreSQL. No agent execution or state write was added.

**Implementation record:** Added `StageDependencyResolver`, immutable `StageSnapshot` and `StageReadiness` results. For each graph stage, only a `SUCCEEDED` predecessor from the current generation satisfies a dependency. Unmet dependencies produce `BLOCKED`; all met dependencies produce `READY` for pending-like stages. Active and terminal stage statuses are preserved. Results follow deterministic graph order and include sorted unmet dependency names. Missing or prior-generation parents do not release children. The resolver reads snapshots only and neither evaluates gates nor persists transitions.

**Verification:** `test_dependency_resolver.py` contains the three mandatory tests plus failure/stale/rolled-back/skipped/cancelled predecessor, wrong-generation, missing-parent, deterministic ordering and input immutability cases. Full `python -m pytest -p no:cacheprovider --require-postgres -q` passed 44 tests, 0 failures/skips. Phase 9 remains the sole planned transition authority.

## PHASE 9 — Deterministic state machine

**Objective:** Make `WorkflowOrchestrator` the sole state authority and atomically audit every transition.

**Exact modules/files expected:** `O/orchestration/state_machine.py`, `O/orchestration/orchestrator.py`, `O/orchestration/commands.py`, `O/api/workflows.py`, `O/api/schemas.py`, `OT/test_state_machine.py`, `OT/test_transition_atomicity.py`, `OT/test_workflow_api.py`.

**Data model changes:** Use optimistic versions/row locks from Phase 6; transition event and entity update share one transaction. Legal workflow and stage tables cover every specification §5.2 state. Retry/replan creates new attempt/generation records instead of rewriting historical outcomes.

**APIs:** `POST /api/v1/workflows`, `GET /api/v1/workflows/{id}`, `POST /api/v1/workflows/{id}/cancel`; creation promptly returns workflow reference. Structured invalid-transition/stale-version conflicts. Agent output has no transition authority. Execution stays disabled until required scheduler/gates exist.

**Dependencies:** Phases 6, 8.

**Tests:** Legal/illegal transition table, competing writers, injected audit failure rolls back state, duplicate commands, cancellation, terminal states, mixed-branch summary precedence, and agent attempts to request success. Completion guard rejects missing required current gates/release approval even before those implementations exist.

**Acceptance criteria:** No publicly writable status field; workflow summaries expose individual branch states; all changes auditable and concurrency-safe; cancelled/failed/completed semantics distinct from recoverable safe-stop.

**Risks:** Direct ORM mutation bypasses and misleading aggregate status. Centralize command handling and review all state write sites.

**Status:** NOT_STARTED — no implementation or tests executed.

## PHASE 10 — OpenAI Agents SDK abstraction

**Objective:** Introduce typed provider contracts, real SDK integration, and deterministic test doubles without granting workflow authority.

**Exact modules/files expected:** `O/agents/provider.py`, `O/agents/openai_provider.py`, `O/agents/fake_provider.py`, `O/agents/contracts.py`, `O/agents/errors.py`, `OT/test_agent_provider.py`, `OT/live/test_sdk_smoke.py`, `docs/decisions/ADR-003-openai-agent-runtime.md`; update Python dependency lock/config.

**Data model changes:** Persist provider mode, actual model/SDK/instruction/schema versions, request trace, turn/time budget, and classified result/error on attempts. Never persist secrets.

**APIs:** Internal `AgentProvider` accepts immutable stage context and authorized tool set and returns validated structured results. `OPENAI_MODEL` is configurable; fake/live mode visible in status/evidence.

**Dependencies:** Phases 5, 9.

**Tests:** Typed output validation, malformed results, timeout/cancellation, fake repeatability, no state/approval access, budget enforcement, explicit live SDK smoke using opt-in credentials. Record live test skipped/failed accurately if unavailable.

**Acceptance criteria:** SDK adapter and fake implement the same contract; live smoke evidence required to verify actual integration; provider errors remain failures, not invented outputs. Configure SDK/client retry behavior to avoid multiplication with Phase 16.

**Risks:** SDK API drift, cost/turn overruns, and confusing fake integration tests with live proof. Verify official SDK contracts when implementing the pinned version.

**Status:** NOT_STARTED — no implementation or tests executed.

## PHASE 11 — Engineering specialist agents

**Objective:** Implement eight bounded engineering specialists and genuinely restricted tools that produce verifiable work.

**Exact modules/files expected:** `O/agents/requirement.py`, `planning.py`, `architecture.py`, `implementation.py`, `testing.py`, `security.py`, `documentation.py`, `release_readiness.py` (each under `O/agents/`); `O/agents/output_schemas.py`, `O/agents/instructions.py`, `O/tools/filesystem.py`, `O/tools/search.py`, `O/tools/commands.py`, `O/tools/dependencies.py`, `O/tools/workspaces.py`, `O/tools/runner.py`, `O/tools/evidence.py`, `O/governance/tool_policy.py`, `O/governance/redaction.py`, `infra/runner/Dockerfile`, `infra/runner/policy.json`, `OT/test_specialist_contracts.py`, `OT/test_tools.py`, `OT/test_runner_isolation.py`.

**Data model changes:** Add `tool_invocations` via `M/0003_tool_invocations.py`: invocation ID, actor/stage/attempt, candidate/input hash, sanitized arguments, command profile, exit code, timestamps, output references, error class. Record initial workspace seed hash and stage-specific output ownership.

**APIs:** Restricted `list_files`, `read_file`, `search_code`, `write_file`, `apply_patch`, `run_build`, `run_tests`, `inspect_dependencies`. Specialists return all fields specified in §8.1; none exposes state mutation or human approval tools.

**Dependencies:** Phases 7, 10. Implement foundational policy here, not in Phase 20.

**Tests:** All eight schemas and tool allowlists; real bounded file edits/build/test evidence; traversal/symlink/secret-path denial; fixed argument arrays, output/file/time bounds; hostile build script cannot access host/API credentials, socket, privileged mounts, or disallowed network; CPU/memory/process limits.

**Acceptance criteria:** Real command exit status determines build/test evidence; isolated execution has no host secrets or CI tokens; trusted control plane alone provisions runner; no candidate execution if runner isolation is unverified. Each specialist has explicit instructions, schema, tools, context versions, and turn/time budget.

**Risks:** An allowlisted build still executes arbitrary candidate code; stage tools leaking credentials; model-generated fake test summaries. Runner isolation and independently attached invocation evidence are mandatory.

**Status:** NOT_STARTED — no implementation or tests executed.

## PHASE 12 — Entry and exit gates

**Objective:** Enforce PASS/FAIL/WAIT at every execution boundary using current, compatible evidence.

**Exact modules/files expected:** `O/orchestration/gates.py`, `O/orchestration/gate_registry.py`, `O/orchestration/evidence_validation.py`, `OT/test_gates.py`; modify default graph and orchestrator.

**Data model changes:** Add `gate_evaluations` through `M/0004_gate_evaluations.py`: gate/version, exact input/candidate hashes, verdict/reasons, evidence refs, evaluation time, generation. Append audit events in the decision transaction.

**APIs:** Internal gate evaluator; expose blocking reasons and evidence in workflow/graph responses.

**Dependencies:** Phases 8, 9, 11.

**Tests:** All §7.1 boundaries; missing/malformed/stale/incompatible artifacts; blocking ambiguity; architecture contents; approved implementation inputs; actual build/test/scanner receipts; release prerequisites. Forged agent text and old candidate reports cannot pass.

**Acceptance criteria:** WAIT blocks without running; FAIL routes to configured failure handling (fail closed until recovery exists); implementation needs current architecture approval; completion requires current release approval; release readiness aggregates build/unit/integration/security/documentation.

**Risks:** Reusing validation against a changed hash, gate evaluation races, or silently interpreting WAIT as PASS. Recheck input/version preconditions when claiming/committing.

**Status:** NOT_STARTED — no implementation or tests executed.

## PHASE 13 — Human approval checkpoints

**Objective:** Bind authenticated decisions to exact artifacts and provide human clarification before ambiguous work proceeds.

**Exact modules/files expected:** `O/governance/approvals.py`, `O/governance/auth.py`, `O/orchestration/clarifications.py`, `O/api/approvals.py`, `O/api/clarifications.py`, `OT/test_approvals.py`, `OT/test_clarifications.py`, `OT/test_reviewer_auth.py`.

**Data model changes:** Use Phase 6 approvals/clarifications/requirements; enforce unique decision request ID, optimistic version and approved input fingerprint; store reviewer, reason, time, type (`ARCHITECTURE`, `HIGH_IMPACT_CHANGE`, `ASSUMPTION`, `RELEASE`), state (`PENDING`, `APPROVED`, `REJECTED`, `INVALIDATED`). Answers create new immutable requirement/analysis generation.

**APIs:** GET/POST `/api/v1/workflows/{id}/approvals` and `/clarifications`. Approval POST carries approval ID, artifact version/hash, reason and concurrency precondition; duplicate identical decisions return the prior result, conflicting/stale decisions reject. Separate documented local reviewer credentials from agent credentials.

**Dependencies:** Phases 6, 9, 12.

**Tests:** Pause before implementation/release; approval/rejection/resubmission; stale hash and affected-input invalidation; duplicate decisions; agent impersonation; high-impact schema/API/security and material assumption approvals; clarification blocks implementation then resumes analysis in new generation after answers.

**Acceptance criteria:** Rejection never permits descendants; new artifact requires new approval; no timeout/default auto-approval; blocking clarification persists across restart. Phase 19 will extend baseline regeneration to selective updates of completed work.

**Risks:** A claimed actor name mistaken for authentication, lost approval during restart, and blanket approval covering unrelated future changes.

**Status:** NOT_STARTED — no implementation or tests executed.

## PHASE 14 — Parallel stage execution

**Objective:** Execute independent ready stages concurrently with durable, unique claims and bounded resources.

**Exact modules/files expected:** `O/orchestration/scheduler.py`, `O/orchestration/claims.py`, `O/orchestration/worker.py`, `O/orchestration/cancellation.py`, `M/0005_stage_claim_constraints.py`, `OT/test_parallel_execution.py`, `OT/test_stage_claims.py`, `OT/test_restart_recovery.py`.

**Data model changes:** Partial unique active-claim constraint; lease owner/expiry/heartbeat, fencing token, stage timestamps, and durable recovery state. Expired lease is not proof that uncertain tool effects may be replayed.

**APIs:** Internal scheduler/claim/heartbeat interfaces; workflow status exposes active stages and provider; `MAX_PARALLEL_STAGES` default 3. Cancellation stops claims and fences late results.

**Dependencies:** Phases 9, 11, 12, 13.

**Tests:** Barrier-controlled independent stages overlap in time; concurrency cap; two competing schedulers claim once; lost lease, process interruption, graceful shutdown, cancellation, stale-token result rejection; successful work not rerun after restart.

**Acceptance criteria:** No shared mutable stage outputs; claim and eligibility checks atomic; only current claim/generation can commit; pending approvals survive restart; uncertain effects enter reconciliation/fail-closed path. Engineering joins are enabled only after Phase 15.

**Risks:** Duplicate execution after lease expiry, cancellation races, event-loop blocking, and falsely claiming exactly-once external effects.

**Status:** NOT_STARTED — no implementation or tests executed.

## PHASE 15 — Synchronization joins

**Objective:** Assemble compatible stage outputs and prevent downstream progress until every mandatory branch passes.

**Exact modules/files expected:** `O/orchestration/joins.py`, `O/artifacts/candidates.py`, `O/tools/overlays.py`, `OT/test_synchronization_joins.py`, `OT/test_candidate_assembly.py`; update graph/gates/scheduler.

**Data model changes:** Candidate manifests are immutable artifacts recording base hash, contributing overlay hashes, test design, exact input versions, generation, and conflict/assembly evidence. No new table required.

**APIs:** Internal join evaluation and candidate assembly; graph/status includes waiting parents and conflict reasons.

**Dependencies:** Phases 8, 12, 14.

**Tests:** Delayed test design blocks build; delayed security blocks documentation finalization; incompatible versions and conflicting writes reject assembly; failed/stale/rolled-back parents cannot satisfy join; explicit optional skip; read-only validation snapshots with independent output directories/databases.

**Acceptance criteria:** Implementation/test-design/documentation fan-out and unit/integration/security fan-out are real; build joins implementation+test design; final documentation joins all validation branches+draft. No concurrent Maven builds share mutable `target/`.

**Risks:** Merging unrelated generations, nondeterministic overlay order, treating “started” as “succeeded,” and stale join decisions.

**Status:** NOT_STARTED — no implementation or tests executed.

## PHASE 16 — Retry, fallback and safe-stop

**Objective:** Recover bounded transient failures while making unsafe/uncertain work stop visibly and durably.

**Exact modules/files expected:** `O/orchestration/retries.py`, `O/orchestration/fallback.py`, `O/orchestration/recovery.py`, `O/orchestration/failure_classifier.py`, `O/api/recovery.py`, `OT/test_retry_policy.py`, `OT/test_fallback.py`, `OT/test_safe_stop.py`; update provider/scheduler.

**Data model changes:** Persist next retry time, classified cause, attempt count, fallback provenance, incident start/resolution, last successful stage, stop reason and recommended action using Phase 6 tables. Each new attempt is distinct.

**APIs:** `POST /api/v1/workflows/{id}/resume` authenticates human recovery and validates resolved cause/current inputs/approvals; status reports actionable stop details. Resume is not a raw status reset.

**Dependencies:** Phases 9, 10, 14, 15.

**Tests:** Exactly two total default attempts; bounded backoff/jitter under controlled clock; transient-only retry; assertions/policy/security errors never auto-retry; no multiplied SDK retry loop; uncertain-effect reconciliation; permitted fallback schema/gate/provenance; unsupported fallback safe-stops; cancellation/drain and late-result fencing; denied premature resume.

**Acceptance criteria:** Exhaustion safely stops unless configured fallback passes the same gates; fallback cannot invent tests/security/approval or arbitrary implementation; no descendants execute after stop; recovery is explicitly human-requested and audited.

**Risks:** Retry storms, repeated side effects, hidden client retries, fallback masking failure, and bypassed approval on recovery.

**Status:** NOT_STARTED — no implementation or tests executed.

## PHASE 17 — Rollback/compensation

**Objective:** Reject failed candidates safely while preserving previous approved state and complete failure evidence.

**Exact modules/files expected:** `O/orchestration/compensation.py`, `O/artifacts/candidate_refs.py`, `M/0006_compensations.py`, `OT/test_compensation.py`, `OT/test_compensation_recovery.py`.

**Data model changes:** `compensations` keyed by workflow/candidate/cause for idempotency; source/restored references and progress. Append lifecycle `ROLLED_BACK` metadata without deleting content; preserve previous approved candidate pointer.

**APIs:** Internal compensation command triggered by mandatory downstream validation failure; workflow/audit/artifact APIs expose result and restored reference.

**Dependencies:** Phases 6, 13, 15, 16.

**Tests:** Stop/fence descendants; `ROLLBACK_STARTED`/`ROLLBACK_COMPLETED`; restore approved reference; no-prior-candidate case; duplicate compensation; crash between steps; derived evidence/approval invalidation; compensation failure safe-stop.

**Acceptance criteria:** Rejected content/evidence retained; prior approved state preserved; idempotent crash recovery; no invented restored release. Scope is local candidate compensation, not deployed infrastructure or irreversible database rollback.

**Risks:** Deleting diagnostic artifacts, restoring unapproved candidate, pointer/filesystem divergence, and overclaiming distributed rollback.

**Status:** NOT_STARTED — no implementation or tests executed.

## PHASE 18 — Artifact versioning and lineage

**Objective:** Complete immutable artifact lifecycle, cross-stage context, and decision lineage queries on the Phase 6 foundation.

**Exact modules/files expected:** `O/artifacts/lineage.py`, `O/artifacts/decisions.py`, `O/artifacts/lifecycle.py`, `O/api/artifacts.py`, `O/api/lineage.py`, `M/0007_lineage_indexes.py`, `OT/test_lineage.py`, `OT/test_artifact_api.py`, `docs/decisions/ADR-004-artifact-lineage.md`.

**Data model changes:** Index existing lineage by exact parent/child versions and stable requirement/component IDs; validate `DERIVED_FROM`, `IMPLEMENTS`, `VALIDATES`, `DOCUMENTS`, `SUPERSEDES`; append decisions/rationales/alternatives and lifecycle events. Never rewrite historical content.

**APIs:** GET `/api/v1/workflows/{id}/artifacts`, `/artifacts/{artifact_id}`, `/lineage`; paginated inventories and size/access-limited content. Return producer, exact inputs, generation, schema, hash and related decisions.

**Dependencies:** Phases 6, 13, 17.

**Tests:** Requirement-to-release traversal, hash/version identity, exact producer attempts, component-level edges, lifecycle history, missing/corrupt references, unauthorized/cross-workflow reads, pagination, approval binding preserved through supersession/rollback.

**Acceptance criteria:** Reviewer can reconstruct why an output exists and which inputs/evidence/decisions it uses; previous versions remain inspectable; lineage corruption blocks dependent execution.

**Risks:** Only storing prose lineage, overly broad dependencies preventing reuse, leaking artifact secrets, and durable URI content changing beneath a stable hash.

**Status:** NOT_STARTED — no implementation or tests executed.

## PHASE 19 — Dynamic selective re-planning

**Objective:** Recompute only affected work after upstream changes while renewing aggregate validation and governance.

**Exact modules/files expected:** `O/orchestration/replanning.py`, `O/artifacts/impact.py`, `O/api/requirements.py`, `OT/test_replanning.py`, `OT/test_replan_races.py`; extend graph/approval/lineage services.

**Data model changes:** New immutable requirement and graph generations; typed reuse references to unaffected artifacts; audited affected closure, stale lifecycle markers and invalidated approvals. Preserve obsolete in-flight attempts as history.

**APIs:** `POST /api/v1/workflows/{id}/requirements` with update/idempotency identity and expected version; promptly return revised workflow reference. Reject stale/conflicting updates and invalid graph contracts.

**Dependencies:** Phases 7, 9, 13, 16, 18.

**Tests:** Change expired-link requirement from `404` to `410`; stable requirement/component comparison; traverse lineage+DAG closure; stale redirect design/code/tests/API docs and affected approvals; preserve independent analytics artifact; fence late old-generation results; rerun changed-candidate aggregate tests and release gates; concurrent updates; revised graph cycles rejected.

**Acceptance criteria:** Only affected producers and necessary aggregation gates rerun; unaffected artifacts have explicit validated reuse references; old whole-candidate evidence is never reused for a new candidate hash; new approvals required where inputs changed.

**Risks:** Under-invalidation, indiscriminate full reruns, new-generation cycles, and treating component reuse as whole-release validation.

**Status:** NOT_STARTED — no implementation or tests executed.

## PHASE 20 — Policy guardrails

**Objective:** Unify security, local compliance controls, change control, and controlled autonomy under versioned deterministic policies.

**Exact modules/files expected:** `O/governance/policy.py`, `O/governance/rules.py`, `O/governance/security_findings.py`, `apps/orchestrator/config/policies.yaml`, `OT/test_policy_engine.py`, `OT/test_guardrail_abuse.py`, `docs/SECURITY.md`; extend Phase 11 tool policy/auth/redaction and all gates.

**Data model changes:** Version/hash every policy set; persist `ALLOW`, `DENY`, `REQUIRE_APPROVAL` with rule ID/version, actor/tool, reason, artifact refs and audit event. Clarify distinction from gate PASS/FAIL/WAIT.

**APIs:** Internal policy evaluation at tool, stage, approval, replan, recovery and release boundaries; structured denial or approval-needed response. Do not add arbitrary policy execution from YAML.

**Dependencies:** Phases 11, 12, 13, 16, 19.

**Tests:** Traversal/symlink/secret/host-mount/socket escape, forbidden command/argument, resource budget, spoofed reviewer, stale approval, cross-workflow access, instructions embedded in repository/requirements/tool output, tampered scanner evidence, severity blocking rules, redaction.

**Acceptance criteria:** Default deny for unregistered capabilities; high-impact actions require human authorization; tool outputs cannot modify rules; model-only security review is labeled distinctly from scanners; security/compliance/change-control rules are explicit without claiming regulatory certification.

**Risks:** Prompt instructions masquerading as authority, inconsistent enforcement across call sites, arbitrary-code config, and undocumented production identity/network gaps.

**Status:** NOT_STARTED — no implementation or tests executed.

## PHASE 21 — Audit trail and reliability metrics

**Objective:** Complete causally ordered audit coverage and compute required reliability measures from actual durable events.

**Exact modules/files expected:** `O/observability/events.py`, `O/observability/metrics.py`, `O/observability/reporting.py`, `O/api/audit.py`, `O/api/metrics.py`, `OT/test_audit_coverage.py`, `OT/test_metrics.py`, `docs/METRICS.md`.

**Data model changes:** Add reporting indexes via `M/0008_observability_indexes.py`; record missing wait/incident interval boundaries in existing audit/incident records; derived reporting may be rebuilt from durable data. No high-cardinality workflow labels.

**APIs:** Paginated GET `/api/v1/workflows/{id}/audit`, root GET `/metrics`; add GET `/api/v1/metrics/summary` for CLI ratios/windows/N/A where raw Prometheus text is insufficient (explicit plan extension). Restrict detail access and sanitize metadata.

**Dependencies:** Phases 9, 16, 17, 19, 20.

**Tests:** Known clock/event fixtures verify event coverage, actor identity, causal ordering, redaction, pagination and restart-stable reporting. Verify zero denominators and exclusion/inclusion cohorts, duplicate processing and unresolved incidents.

**Acceptance criteria:** Report success = completed/(completed+failed), cancelled/safe-stopped separately; retry frequency = retry attempts/initial attempts with counts; rollback frequency = workflows with compensation/workflows started in declared cohort; MTTR = failure-to-successful-recovery for resolved incidents, unresolved separately; end-to-end = creation-to-completion including human wait, with execution/wait components. Document window/cohort selection. Expose started/completed/safe-stopped/policy counters, durations, retry/rollback counters, and pending-approval gauge. `approval_waiting_total`, if present, counts entries rather than queue size. Audit all transitions, tools, artifacts, gates, decisions, approvals, clarifications, retries, fallbacks, compensation, replans, denials, recovery.

**Risks:** Counter double-counting on restart, biased denominators, unbounded labels, and calling ordinary log text an audit trail.

**Status:** NOT_STARTED — no implementation or tests executed.

## PHASE 22 — Terminal CLI

**Objective:** Provide a complete Typer/Rich reviewer interface using only orchestrator APIs.

**Exact modules/files expected:** `O/cli/main.py`, `O/cli/client.py`, `O/cli/workflow.py`, `O/cli/approval.py`, `O/cli/artifact.py`, `O/cli/clarification.py`, `O/cli/requirement.py`, `O/cli/audit.py`, `O/cli/metrics.py`, `O/cli/demo.py`, `O/cli/rendering.py`, `OT/test_cli.py`, `OT/test_cli_api_contract.py`; update package `agentic` entry point.

**Data model changes:** None; CLI has no DB credentials/writes. Securely configure API URL/local reviewer credential without printing it.

**APIs:** Commands: `agentic workflow create|status|watch|graph|resume|cancel`; `approval list|approve|reject`; `artifact list|show`; `lineage`; `clarification list|answer`; `requirement update`; `audit`; `metrics`; `demo greenfield|brownfield|ambiguous`. Map to earlier APIs. Demo command framework may report fixtures unavailable until Phases 23–25; those scenarios are not claimed complete here.

**Dependencies:** Phases 13, 18, 19, 21.

**Tests:** CliRunner plus API contract tests: approval artifact/diff/risk/version display, no automatic accept, stale decision conflict, structured errors/exit codes, JSON and no-color, narrow terminal, bounded polling/backoff, Ctrl-C watch leaves workflow running, pagination, secrets absent.

**Acceptance criteria:** Status shows scenario/provider/stages/blocked reasons/next action; graph and lineage readable; explicit human decisions carry version preconditions; CLI uses no private state shortcuts.

**Risks:** Pretty output hiding failure, approval against a refreshed artifact without consent, endless polling, and credentials in command history.

**Status:** NOT_STARTED — no implementation or tests executed.

## PHASE 23 — Greenfield scenario

**Objective:** Demonstrate requirement-to-reviewable-engineering output from a minimal buildable seed.

**Exact modules/files expected:** `scenarios/greenfield/requirement.md`, `scenarios/greenfield/scenario.yaml`, `scenarios/greenfield/seed/pom.xml`, `scenarios/greenfield/seed/src/main/java/com/schwab/urlshortener/UrlShortenerApplication.java`, `scenarios/greenfield/seed/src/main/resources/application.yml`, `scenarios/greenfield/seed/src/test/java/com/schwab/urlshortener/BootstrapTest.java`, `scenarios/greenfield/seed/README.md`, `O/scenarios/runner.py`, `O/scenarios/evidence.py`, `OT/scenarios/test_greenfield.py`, `OT/live/test_live_engineering_workflow.py`, `docs/scenarios/GREENFIELD.md`; add fake fixtures under `OT/fixtures/greenfield.json`.

**Data model changes:** No production schema; workflow artifacts capture seed/final hashes, real changes, requirement/task mapping, approvals, build/test/security/doc results and release manifest.

**APIs:** Existing workflow/approval/artifact APIs; `agentic demo greenfield`. Fixture approvals use explicitly identified test actors through approval API.

**Dependencies:** Phases 4, 15, 17, 20, 22 and their transitive prerequisites. Use existing runner/test infrastructure before Compose packaging.

**Tests:** Deterministic end-to-end scenario, actual candidate compile/unit/integration tests, unapproved pause, parallel overlap and joins; injected transient retry/configured fallback, safe-stop and compensation variants. Separate opt-in live engineering workflow must make actual file changes and execute tools.

**Acceptance criteria:** Seed is not the completed product; generated candidate implements stated scope with executable validation; decomposition, governance, test/doc creation and release approval visible. Both repeatable fake evidence and at least one successful live engineering run are required for full verification; report missing live evidence honestly.

**Risks:** Prebuilt outputs presented as generated work, fake transcript substituted for execution, flaky model results, and uncontrolled candidate dependencies.

**Status:** NOT_STARTED — no implementation or tests executed.

## PHASE 24 — Brownfield scenario

**Objective:** Enhance an existing creation/redirect service with aliases and expiration while preserving behavior and data.

**Exact modules/files expected:** `scenarios/brownfield/requirement.md`, `scenarios/brownfield/scenario.yaml`, `scenarios/brownfield/seed/pom.xml`, `scenarios/brownfield/seed/README.md`; under `scenarios/brownfield/seed/src/main/java/com/schwab/urlshortener/`: `UrlShortenerApplication.java`, `api/LinkController.java`, `api/RedirectController.java`, `application/LinkService.java`, `application/RedirectService.java`, `domain/Link.java`, `domain/ShortCodeGenerator.java`, `persistence/LinkRepository.java`; seed `src/main/resources/application.yml`, `src/main/resources/db/migration/V1__create_links.sql`, `src/test/java/com/schwab/urlshortener/CoreRegressionTest.java`; `OT/scenarios/test_brownfield.py`, `OT/fixtures/brownfield.json`, `docs/scenarios/BROWNFIELD.md`.

**Data model changes:** Existing seed links intentionally lack new feature fields; generated candidate adds forward migration for alias/expiry while preserving seeded records. Keep this seed's migration history separate from the finished product's V1–V3 history.

**APIs:** Existing create/redirect contract retained; generated candidate adds alias/expiry behavior with documented API/schema diff and high-impact approval.

**Dependencies:** Phases 3, 23.

**Tests:** Baseline create/redirect before edits; inspect actual seed files before planning; impacted module/API/data-flow mapping; new alias/conflict/expiry `410` tests; old records survive upgrade; original regression suite still passes. Fault variants prove safe-stop/compensation with retained previous-approved candidate.

**Acceptance criteria:** Evidence shows code inspection, actionable decomposition, real diff/migration, before/after tests, approved changes, updated OpenAPI/docs and release evidence. Seed remains immutable across repeated demos.

**Risks:** Copying the complete product into the seed, inventing nonexistent impacted files, destructive migration, and tests passing only on empty databases.

**Status:** NOT_STARTED — no implementation or tests executed.

## PHASE 25 — Ambiguous requirement scenario

**Objective:** Demonstrate human clarification and selective replanning with visible preserved and invalidated work.

**Exact modules/files expected:** `scenarios/ambiguous/requirement.md`, `scenarios/ambiguous/scenario.yaml`, `scenarios/ambiguous/answers.json`, `scenarios/ambiguous/expiry-change.md`, `scenarios/ambiguous/seed/README.md`, `scenarios/ambiguous/seed/source-manifest.json`, `OT/scenarios/test_ambiguous.py`, `OT/fixtures/ambiguous.json`, `docs/scenarios/AMBIGUOUS.md`.

**Data model changes:** No new production tables; persist questions/answers, stable acceptance IDs, revised requirement/graph generation, affected closure, reuse references and renewed approvals. Seed source manifest pins a preserved prior seed/candidate snapshot; preparation materializes and verifies it before execution.

**APIs:** `agentic demo ambiguous`, clarification answer, requirement update, approval and lineage commands through established APIs.

**Dependencies:** Phases 19, 23, 24.

**Tests:** “Make links safer” yields questions about acceptance, malicious URLs, HTTPS, expiry, private/local destinations and authentication; zero implementation invocations while waiting; human answers version context; approved assumptions permit progression. Separate checkpoint changes earlier expiry `404` to final `410`, invalidates affected descendants/approvals, retains independent analytics, reruns aggregate validation and obtains renewed release approval. Inject late results during replan.

**Acceptance criteria:** All three assignment scenarios show decomposition, orchestration and validation; ambiguity is not silently guessed away; final product follows `410`; evidence includes changed hashes, stale/reused artifacts and fresh candidate validation.

**Risks:** Baking answers into the model, counting a no-op update as replanning, and preserving stale whole-candidate tests.

**Status:** NOT_STARTED — no implementation or tests executed.

## PHASE 26 — Docker Compose

**Objective:** Package the verified local system into a reproducible reviewer startup with durable storage and restricted execution.

**Exact modules/files expected:** `docker-compose.yml`, `apps/url-shortener/Dockerfile`, `apps/orchestrator/Dockerfile`, `infra/postgres/init-databases.sh`, `scripts/health-check.sh`, `scripts/smoke-test.sh`, `scripts/test-compose.sh`, `.dockerignore`; update runner files, `.env.example`, `Makefile`, `README.md`.

**Data model changes:** Provision separate URL/orchestrator databases and roles on one PostgreSQL server; named persistent volumes; each service runs only its own migration history. No destructive reset in normal shutdown.

**APIs:** Loopback-bound URL/orchestrator endpoints and documented CLI execution path; `make up`, `down`, `health`, `test`, `lint`, `demo`, `smoke`; destructive reset, if supplied, explicitly separate. Default fake mode, live explicitly selected.

**Dependencies:** Phases 4, 5, 11, 22–25.

**Tests:** Clean checkout/env setup/build/start; health/readiness wait; migrations, URL smoke and minimal workflow; all scenario entry points; restart preserves links/workflows/approvals; graceful shutdown; cross-role DB access denied; keys absent from candidate runner; resource/mount/network boundaries and non-root app users.

**Acceptance criteria:** Documented reviewer sequence works; images pinned; persistent data survives `make down`; trusted provisioning boundary cannot be reached by agents; first-build downloads/prerequisites honestly documented.

**Risks:** Docker socket leaking into control-plane tools, migration races, platform-specific images, privileged runner, and false offline-start claims.

**Status:** NOT_STARTED — no implementation or tests executed.

## PHASE 27 — GitHub Actions CI

**Objective:** Automate reproducible validation of both services, governance scenarios, packaging, and security controls.

**Exact modules/files expected:** `.github/workflows/ci.yml`, `.github/workflows/live-verification.yml`, `.gitleaks.toml`, `scripts/ci-security.sh`; update `docs/TESTING.md` and evidence export scripts.

**Data model changes:** None; isolated ephemeral test databases and sanitized report artifacts only.

**APIs:** GitHub push/PR triggers for ordinary CI; explicitly dispatched protected live verification. No live-model API keys for untrusted PRs or candidate execution.

**Dependencies:** Phase 26.

**Tests:** Java 21 Maven verify/Testcontainers and formatting; locked Python lint/pytest/PostgreSQL; all three fake scenarios with explicit approvals; image builds/Compose config; stack readiness/smoke/cleanup; dependency and secret scans. Check failure report preservation and least-privilege permissions.

**Acceptance criteria:** Actual CI run passes required jobs; reviewed actions pinned to immutable references; reports retained on failure; live job is opt-in, separately labeled and protected; coverage reported without an invented threshold.

**Risks:** Docker runner constraints, dependencies/download failures, unsafe PR secret exposure, leaked CI tokens, and suppressing scan findings to obtain a green badge.

**Status:** NOT_STARTED — no implementation or tests executed.

## PHASE 28 — Documentation and final demo

**Objective:** Deliver a defensible final engineering summary and reproducible reviewer experience backed by actual evidence.

**Exact modules/files expected:** `README.md`, `docs/ARCHITECTURE.md`, `docs/DEMO.md`, `docs/TESTING.md`, `docs/SECURITY.md`, `docs/LIMITATIONS.md`, `docs/METRICS.md`, `docs/FINAL_ENGINEERING_SUMMARY.md`, `docs/FINAL_REVIEW.md`, `docs/TRACEABILITY.md`, `docs/decisions/ADR-001-service-boundaries.md`, `ADR-002-deterministic-orchestration.md`, `ADR-003-openai-agent-runtime.md`, `ADR-004-artifact-lineage.md`, `ADR-005-analytics-design.md` (all ADRs under `docs/decisions/`), `docs/scenarios/GREENFIELD.md`, `BROWNFIELD.md`, `AMBIGUOUS.md` (all under `docs/scenarios/`), `IMPLEMENTATION_PLAN.md`; real run evidence under the evidence convention above.

**Data model changes:** None. Export sanitized immutable evidence manifests and final requirement-to-evidence links.

**APIs:** Document all implemented endpoints/CLI commands, errors, auth, provider modes, configuration, recovery and migration procedures; no new product API.

**Dependencies:** Phase 27 and every prior acceptance gate, including live SDK smoke/live engineering evidence.

**Tests:** Rehearse clean-start instructions and all three scenarios from a fresh checkout; reproduce required failure controls and replanning; verify every traceability link/report/hash; compare OpenAPI and architecture diagrams to implementation; review secrets/distribution; run final required build/test/lint/smoke commands and record actual results.

**Acceptance criteria:** Summary includes plan/rationale, generated code/API/schema/test/doc artifacts, risks/tradeoffs, validation outcomes, assumptions and limitations. Reviewer can see approvals, overlap/joins, recovery/compensation, lineage, selective reuse and metrics. Every requirement has code, named test, actual outcome and demonstrable evidence; unresolved gaps remain explicitly open. Assignment's production-quality expectation is addressed without unsupported production-readiness claims.

**Risks:** Stale diagrams, fabricated/canned screenshots, missing live evidence, internal PDF published without permission, and unchecked requirements marked complete.

**Status:** NOT_STARTED — no implementation or tests executed.

## Phase completion record template

For each authorized phase, record: commit/diff; changed behavior and schema/API changes; exact commands/environment; passed/failed/skipped results; evidence manifest and requirement IDs; remaining limitations; status and next dependency gate. Stop at the requested phase boundary. The original planning task authored only this document and the traceability matrix. The separately authorized Phase 1 bootstrap and evidence are recorded above; stop before Phase 2.
