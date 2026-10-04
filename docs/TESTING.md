# Testing and verification

## Phase 11 bounded tools — verified on 2026-10-04

**159 tests passed:** 134 unit tests, 18 PostgreSQL tests and seven real
Docker runner tests. One opt-in live OpenAI smoke was skipped.

```sh
cd apps/orchestrator
.venv/bin/python -m pytest -p no:cacheprovider -m 'not integration and not runner' -q
cd ../..
BUILDX_CONFIG=/tmp/schwab-buildx UV_CACHE_DIR=/tmp/schwab-uv-cache make test-runner
UV_CACHE_DIR=/tmp/schwab-uv-cache make test-db
```

The temporary cache variables above accommodate this desktop sandbox; on
an ordinary checkout, `make test-runner` and `make test-db` suffice.
Runner tests fail when explicitly enabled and Docker/image execution fails;
they only skip when `RUN_RUNNER_TESTS` is not enabled. No agent API calls
are involved in Docker verification.

The new tests cover actual file edits/patches/searches, credential/traversal/
link/special-file denial, SDK grants/context boundaries, command and project
injection, successful Maven test/package and pytest runs, real assertion
failure, host-secret exclusion, disabled network, non-root/capability/resource
settings, time/output limits, cancellation and cleanup.
Ruff lint/format (including the trusted runner entry point), structure and
diff checks passed. See [SECURITY.md](SECURITY.md) and
[the evidence manifest](evidence/phase-11-engineering-tools/manifest.json).

## Phases 10–11 — agent contracts verified offline on 2026-10-04

The orchestrator suite passed **105 tests**: 87 non-DB tests and 18 real
PostgreSQL tests. **One live smoke was skipped** because its explicit opt-in
was not enabled. No paid API call or live model engineering result is claimed.

Commands:

```sh
cd apps/orchestrator
.venv/bin/python -m pytest -p no:cacheprovider -m 'not integration' -q
cd ../..
UV_CACHE_DIR=/tmp/schwab-uv-cache make test-db
```

Coverage includes eight strict schemas and tool allowlists, repeatable fake
responses, malformed outputs, actual SDK Runner parsing/tool loops with a
local Model stub, turn exhaustion, deadlines/cancellation, provider error
classification, snapshot access restrictions, and PostgreSQL state/audit
preservation. The adapter test module rejects HTTP requests. The test
`agent_provider` fixture is deterministic; application provider selection
defaults to the real SDK.

For a separately recorded live smoke, export a valid `OPENAI_API_KEY` and
`OPENAI_MODEL`, then run
`RUN_LIVE_AGENT_TESTS=1 uv run --locked python -m pytest tests/live/test_sdk_smoke.py -q`.
An opted-in run fails when credentials/model configuration are missing.
See [the evidence manifest](evidence/phase-10-11-agents/manifest.json) and
[runtime ADR](decisions/ADR-003-openai-agent-runtime.md) for verified scope
and the scope at that delivery; the bounded-runner follow-up is recorded above.

## Phase 9 — verified on 2026-10-04

The full orchestrator suite passed **59 pytest tests, 0 failures, 0 skips**
against disposable PostgreSQL 17.7. Fifteen new state-machine and atomicity
tests cover the requested behavior.

| Check | Test | Actual result |
|---|---|---|
| Legal rules | `test_required_legal_stage_transition_rules` | All seven requested example edges accepted |
| Complete rule tables | `test_every_status_has_an_explicit_transition_rule` | Every workflow and stage enum value has an explicit outgoing set |
| Illegal rules | Parameterized illegal cases and orchestrator integration test | Invalid edge raises before state/version change; no transition audit event |
| Audit creation | Legal stage-chain and workflow transition tests | Before/after state, actor, reason, stage metadata and entity version persisted |
| Atomicity | `test_audit_failure_rolls_back_stage_transition` | Injected audit failure rolls back status and version |
| Authority/concurrency | Direct mutation and stale-version tests | Public status is read-only; guarded internal mutation denied; stale expected version rejected |

The orchestrator uses PostgreSQL row locks and optimistic entity versions.
`COMPLETED` requires the caller to assert verified release gates, but actual
gate evaluation is not implemented in this phase. No agent or stage executor
ran.

## Phase 8 — verified on 2026-10-04

The full orchestrator suite passed **44 pytest tests, 0 failures, 0 skips**
against disposable PostgreSQL 17.7. Twelve new resolver tests include the
three mandatory readiness cases:

| Case | Status input | Verified result |
|---|---|---|
| `A → B` | A `SUCCEEDED` | B `READY` |
| `A → B,C` | A `SUCCEEDED` | B and C both `READY` |
| `B,C → D` | B `SUCCEEDED`, C `RUNNING`; then C `SUCCEEDED` | D stays `BLOCKED`, then becomes `READY` |

The remaining cases verify that failed, stale, rolled-back, skipped,
cancelled, missing and prior-generation parents do not satisfy dependencies.
Resolution is deterministic and leaves its input unchanged. It computes
structural eligibility only; gates, approval, policy, claims and execution
remain separate later phases.

## Phase 7 — verified on 2026-10-04

The complete orchestrator suite passed **32 pytest tests, 0 failures, 0
skips** against a disposable PostgreSQL 17.7 database. Fourteen new graph
tests exercise the default and ambiguity variants, required fan-out/fan-in
dependencies, deterministic hashing, and invalid configuration rejection.
Ruff lint/format checks and the wheel/sdist build passed; the wheel contains
`app/resources/default_sdlc.yaml`.

| Check | Test | Actual result |
|---|---|---|
| Default DAG | `test_graph_validation.py::test_default_graph_has_required_fan_out_joins_and_approval_checkpoints` | All 16 required stages and specified joins/checkpoints present |
| Conditional clarification | `test_graph_validation.py::test_blocking_ambiguity_inserts_clarification_without_cycle` | Seventeenth stage inserted after analysis; decomposition waits on it; graph hash changes |
| Invalid graphs | Cycle, duplicate, unknown-dependency, registry and retry-policy tests | Loader rejects malformed or unregistered configuration before execution |
| Safe loading and identity | YAML duplicate-key/tag and hash tests | Unsafe tags and duplicate keys rejected; equivalent ordering has the same hash |
| Packaging/regressions | `uv build --no-sources`; full pytest | YAML present in wheel; prior health and persistence tests continue to pass |

The graph registry contains symbolic names only. These tests do not execute
agents, evaluate gates or prove parallel scheduling. Graph revision
persistence/API and new-generation re-analysis remain future work.

## Phase 6 — verified on 2026-10-04

The complete orchestrator suite passed **18 pytest tests, 0 failures, 0
skips** against a disposable PostgreSQL 17.7 database. This includes the
Phase 5 health/configuration tests. Ruff lint and format checks passed.

| Check | Test | Actual result |
|---|---|---|
| Seven-table migration | `test_database.py::test_clean_alembic_upgrade` | Alembic upgrades a fresh database to revision `0002_workflow_foundation`; all requested tables exist |
| Persistence and reload | `test_persistence.py::test_all_entities_round_trip_and_reload` | Workflow, two stage attempts, two artifact versions, lineage, decision, approval and eight audit events reload through a new engine |
| Constraints and rollback | `test_persistence.py` | Duplicate stage attempts, orphan FKs, cross-workflow lineage and mismatched artifact input/approval hashes are rejected; failed transaction leaves no workflow or audit event |
| Immutability | `test_artifact_immutability.py` | PostgreSQL rejects artifact/audit updates and deletes, plus audit truncate; old artifact content and audit events remain; concurrent versions are unique |
| Audit ordering | `test_persistence.py::test_audit_pages_remain_causal_under_concurrent_appends` | Five concurrent appends receive distinct per-workflow sequences and paginate in order |

The full run used a newly created loopback-only PostgreSQL container and
`python -m pytest --require-postgres -q` from `apps/orchestrator`. No
workflow scheduling, approval decision, stage transition, agent call or CLI
was exercised. The requested seven tables are present; graph revisions,
requirement versions, policy events, clarifications and recovery incidents
remain for later phases.

## Phase 5 — verified on 2026-10-04

The FastAPI orchestrator foundation passed **9 pytest tests**: five local
tests and four against an isolated, disposable PostgreSQL 17.7 container.
The PostgreSQL fixture is explicit; a missing `POSTGRES_TEST_DSN` fails
when `--require-postgres` is used. No workflow behavior was tested or built.

| Check | Test | Actual result |
|---|---|---|
| Health and secrecy | `test_health.py` | PostgreSQL reachable → 200; unreachable → 503 with trace ID and no connection password |
| Migration | `test_database.py::test_clean_alembic_upgrade` | At the Phase 5 snapshot, only `alembic_version` was created; the current regression test now checks the Phase 6 schema |
| Session lifecycle | `test_database.py::test_session_commits_and_rolls_back` | Committed write retained; exception rolled back later write |
| Config and API boundary | `test_database.py`, `test_bootstrap.py` | Invalid port/log level rejected; password masked; OpenAPI/docs exposed; no workflow route |
| Build/style | Ruff and `uv build --no-sources` | Lint/format passed; wheel and sdist built |

Reproduce from the repository root with Docker running:

```sh
cd apps/orchestrator
uv sync --locked
uv run --locked python -m pytest -m 'not integration' -q
cd ../..
./scripts/test-postgres.sh -q
```

The development Compose database still uses a bootstrap administrator role.
Restricted runtime roles and full application Compose lifecycle belong to
Phase 26. Tests cover local FastAPI and PostgreSQL behavior, not a deployed
service or OpenAI model calls.

## Phase 4 — verified on 2026-10-04

Verification ran from `apps/url-shortener` in the actual repository with
JDK 21, Maven 3.9.16, Docker 29.4.2 and PostgreSQL 17.7 Testcontainers.
The final `mvn verify` run passed **37 JUnit tests, 0 failures, 0 errors,
0 skips**, checked Java formatting and built the executable JAR. It includes
all Phase 2–3 regression tests.

| Check | Test | Actual result |
|---|---|---|
| Event persistence and aggregation | `AnalyticsTest` with PostgreSQL | Link ID, UTC timestamp, origin-only referrer, coarse user-agent and trace ID persisted; two UTC days aggregate correctly |
| Non-counting paths | `AnalyticsTest` | Metadata, missing and expired redirects create no events; unknown analytics code returns 404 |
| Failure isolation | `AnalyticsFailureIsolationTest`, `AnalyticsTimeoutTest` with PostgreSQL | Forced persistence exception, blocked writer and an actual PostgreSQL write timeout all leave valid redirect at 302; failure counter increases |
| Queue rejection | `AnalyticsRecorderTest` | Rejected event does not throw into caller; dropped counter increases |
| Management and metrics | `ObservabilityTest` | Health/readiness, Prometheus, Micrometer metrics and OpenAPI available; sensitive `/actuator/env` unavailable; success counter increases |
| Prior behavior | Phase 2–3 suite | Creation, aliases, expiry, disable, collision, idempotency, rate limiting and database restart tests continue to pass |

The test context needed `@AutoConfigureObservability` to expose Prometheus
inside Spring Boot tests; the first observability check failed without it.
The final complete run passed. The [Phase 4 evidence manifest](evidence/phase-04-analytics/manifest.json)
contains the sanitized Maven log, per-class test summary and source hashes.

Events are written asynchronously, so totals can briefly lag a successful
redirect. If the process stops before a write, a queue is full, or a write
fails, that click can be lost. Analytics is best-effort, not exactly-once.
No retention deletion runs automatically; the privacy and growth limits are
recorded in [ADR-005](decisions/ADR-005-analytics-design.md). This phase did
not test a deployed service, multi-instance ingestion, or the future
orchestrator/CI stack.

### Reproduce Phase 4

With JDK 21, Maven 3.9.16 and Docker running:

```sh
cd apps/url-shortener
mvn verify
```

## Phase 3 — verified on 2026-10-04

This historical record covers Phase 3 only. Verification ran in the actual repository from `apps/url-shortener` with JDK 21,
Maven 3.9.16, Docker 29.4.2 and a digest-pinned PostgreSQL 17.7
Testcontainers image. The final `mvn verify` run passed all 29 JUnit tests
with 0 failures, 0 errors and 0 skips, checked formatting, and built the
executable JAR. The run included Phase 2 regressions and the new Phase 3 cases.

| Check | Test / method | Actual result |
|---|---|---|
| Aliases | `AliasTest` with PostgreSQL | 3/32-character boundaries, case-sensitive names, invalid/reserved rejection, duplicate `409` |
| Expiry | `ExpiryTest` with PostgreSQL and controlled clock | Future-only creation; `302` before expiry, `410` exactly at expiry |
| Collision recovery | `CollisionTest` with injected generator and PostgreSQL | Forced collision then success; exactly five failed attempts and subsequent transaction health |
| Idempotency | `IdempotencyTest` with PostgreSQL | Same key replays original response; changed request `409`; two concurrent identical requests produce one link and record |
| Disable | `DisableLinkTest` with PostgreSQL | Repeatable `204`; disabled redirect `410`; missing `404`; concurrent disable succeeds |
| Rate limit | `RateLimitTest`, `RateLimitApiTest` | Capacity/window reset, create-only counting, HTTP `429` and `Retry-After` |
| Migration and regressions | `LinkPersistenceTest` and Phase 2 suite | Flyway V1/V2 recorded, database uniqueness, create/metadata/redirect and restart persistence |

The final command was `mvn verify`; its complete sanitized log and test
summary are referenced by the [Phase 3 manifest](evidence/phase-03-reliability/manifest.json).
An earlier failed HTTP-level rate-limit test exposed a path-matching issue in
MockMvc. Matching the request URI fixed it; the final complete run passed.
No tests were skipped because Docker was unavailable. The first sandboxed
attempt lacked Docker socket/process-attach access; granting local Docker
access and selecting Mockito's subclass test mock maker allowed the PostgreSQL
suite to run. The final result is based on the successful full run.

The limiter is one bounded global window per process with default capacity 60
and a one-minute window. It is not shared across instances and resets on
restart. Idempotency currently uses the anonymous caller scope; records have
no automatic expiry. These are prototype limits, not claims of authenticated
caller isolation or distributed throttling. No analytics or orchestrator
behavior was implemented or tested in Phase 3.

### Reproduce Phase 3

With JDK 21, Maven 3.9.16 and Docker running:

```sh
cd apps/url-shortener
mvn verify
```

## Phase 2 — verified on 2026-10-04

This historical record covers Phase 2 only. The Java URL shortener core was installed in the actual repository and verified
from `apps/url-shortener` with JDK 21, Apache Maven 3.9.16, Docker 29.4.2 and
the digest-pinned PostgreSQL 17.7 Testcontainers image. Maven's validation phase
also ran the Java formatting check. The test reports include real PostgreSQL
integration tests; no database test was skipped.

| Check | Command / method | Actual result |
|---|---|---|
| Core tests | `mvn test` | Passed; 15 tests, 0 failures, 0 errors, 0 skipped |
| Executable package | `mvn package` | Passed; 15 tests, 0 failures, 0 errors, 0 skipped; executable JAR built |
| HTTP contract | `LinkApiTest` with PostgreSQL Testcontainers | `201` create, metadata read, `302` redirect with original `Location`, structured `404`, invalid/unsupported input `400`, OpenAPI and health availability |
| Database contract | `LinkPersistenceTest` with PostgreSQL Testcontainers | Flyway V1 applied on a fresh database; persisted row reloads; duplicate short codes fail the database unique constraint |
| Restart persistence | `LinkRestartTest` with PostgreSQL Testcontainers | Link remains readable after closing and reopening the Spring application context against the same database |
| Unit contracts | `LinkServiceTest`, `UrlValidationTest`, `ShortCodeGeneratorTest` | Service mapping, URL validation and seven-character Base62 generation pass |

The tests used the repository's Spring Boot configuration with database
properties supplied by Testcontainers. They did not require a local `.env` or
modify the Compose databases. The package output is
`apps/url-shortener/target/url-shortener-0.1.0-SNAPSHOT.jar` and is ignored by
Git. The tests and command logs are recorded in the
[Phase 2 evidence manifest](evidence/phase-02-core/manifest.json).

The Phase 2 API supports only generated codes and active links. The schema has
nullable `expires_at` and an `ACTIVE`/`DISABLED` status for later phases, but
expiry and disable behavior are not implemented. A random-code collision is
rejected by PostgreSQL uniqueness; retry handling, custom aliases, idempotency,
rate limiting and analytics are Phase 3–4 work. The `analytics` package is an
empty boundary. No orchestrator, scenario, full application Compose stack or CI
test is claimed by this phase.

### Reproduce Phase 2

With JDK 21, Maven 3.9.16 and Docker running:

```sh
cd apps/url-shortener
mvn test
mvn package
```

The two commands each execute the full unit and PostgreSQL Testcontainers test
suite. The test image and Maven dependencies may need downloading on a fresh
machine.

## Phase 1 — verified on 2026-10-04

This historical record covers Phase 1 only. Verification ran from the actual repository after the bootstrap files were installed.
At that point, no product endpoints, persistence models, workflow engine,
agents, migrations or scenario functionality were implemented. The Phase 1
tests verified only the application shells, build configuration and database
test infrastructure.

| Check | Command / method | Actual result |
|---|---|---|
| Locked Python installation | `make bootstrap` (`uv sync --locked`) | Passed; 29 packages resolved, project installed |
| Directory/build structure | `make structure` | Passed; 12 directories, 11 required files and Java/FastAPI configuration checked |
| Compose syntax | `make compose-config` | Passed with example environment; no real secrets required |
| Java formatting | `make lint` / `spotless:check` | Passed for both Java source files |
| Python lint/formatting | `make lint` / Ruff | Passed, including the structure-check script |
| Spring Boot build/tests | `make build` → `./mvnw --batch-mode verify` | Passed; executable JAR built; 2 tests, 0 failures, 0 errors, 0 skipped |
| Python distributions | `make build` → `uv lock --check && uv build --no-sources` | Passed; wheel and source distribution built |
| FastAPI bootstrap | `make test-python` | Passed; 3 tests, 0 failures; database test deliberately deselected |
| Real PostgreSQL connectivity | `make test-db` | Passed; 1 integration test, 0 failures; 3 bootstrap tests deselected |
| Compose lifecycle | `make up`, `make health`, `make down` with isolated test project | Both databases became healthy; down preserved both named volumes |
| Git exclusions | `git check-ignore` checks | Secrets, caches, targets and generated workspaces ignored; examples, lockfile, wrapper and `.gitkeep` trackable |
| Python wheel contents | Inspect built wheel | Application package included; caches excluded |
| Deferred commands | `make demo`, `make smoke` | Both reject use with explicit Phase 1 message and nonzero status |
| Source preservation | SHA-256 comparison | Original AGENTS, specification and assignment unchanged |

The Docker fixture and Compose verification used disposable containers. The
Compose check used a unique project name and random loopback host ports, confirmed
that `make down` preserved its volumes, and then removed only its own test volumes.
No existing user containers or volumes were removed. No `.env` or API key was
created. No Git commit or remote publication was performed.

### Verified environment

- macOS ARM64; Java 21.0.1; Apache Maven 3.9.16; Maven Wrapper 3.3.4.
- Spring Boot 3.5.16; Spotless 3.10.3; Google Java Format 1.28.0 (AOSP style).
- Python 3.12.13; uv 0.11.8; FastAPI 0.142.2; Pydantic 2.13.5; Uvicorn 0.54.0.
- pytest 9.1.1; pytest-asyncio 1.4.0; Ruff 0.16.10; Hatchling 1.32.4.
- Docker Engine/client 29.4.2; Compose 5.1.3 (the `docker compose` plugin).
- PostgreSQL image `postgres:17.7-alpine`, pinned to digest
  `sha256:bb377b7239d2774ac8cc76f481596ce96c5a6b5e9d141f6d0a0ee371a6e7c0f2`.

The execution environment redirected uv/Python/Maven caches into the chat's
writable workspace and selected the installed JDK 21 via `JAVA_HOME`. These are
verification-environment overrides, not repository hardcoded paths. Normal local
use follows the root README. First-run dependencies and Docker images require
network access; no offline-start claim is made.

### Reproduce

With JDK 21 selected, uv 0.11.8 installed, and Docker running:

```sh
make bootstrap structure compose-config lint build test-python
make test-db
```

`make build` already executes Java verification. `make test` is also available
to run Java verification plus the Python bootstrap tests without packaging Python.
`make test-db` explicitly requires a working PostgreSQL fixture and cannot
report a passing database check by skipping it.

Compose normally reads a local `.env` copied from `.env.example`. The verification
used `COMPOSE='docker compose --project-name <disposable-project> --env-file .env.example'`
with `URL_DB_PORT=0` and `ORCHESTRATOR_DB_PORT=0` to avoid occupying normal demo
ports. This is database bootstrap verification, not the Phase 26 application stack.

### Evidence and limitations

See [the Phase 1 manifest](evidence/phase-01-bootstrap/manifest.json) and its
sanitized command transcripts. Earlier interrupted attempts exposed and resolved
an unsupported `uv build --locked` option, selection of system Python for the
structure check, and a Ruff line-length failure. Docker was initially unavailable;
the final connectivity and lifecycle checks passed once it was running.

Two dependency warnings remain non-fatal: Mockito's dynamic-agent attachment
warning on JDK 21 and Starlette's deprecation warning for its HTTPX TestClient
compatibility path. They did not fail tests and are not suppressed. Revisit these
when changing JDK/test-client versions. No coverage threshold or production-readiness
claim is established. No live model calls or later-phase tests were run.
