# Schwab Agentic Engineering

Monorepo for a Spring Boot URL shortener and a deterministic FastAPI SDLC
orchestrator. **Phases 10–11 agent layer:** the Spring Boot service creates and resolves short
links with reliability controls, asynchronous click analytics, and operational
metrics. FastAPI now persists workflow identity, stage attempts, immutable
artifacts, lineage, decisions, approval requests and audit events. Its SDLC
graph is configurable and validated, a pure dependency resolver computes stage
readiness, and a transactional orchestrator owns legal state changes with
atomic audit events. Eight typed specialists now use an OpenAI Agents SDK
provider or an explicit deterministic test provider. Bounded engineering tools
edit only the assigned workflow workspace and run fixed Maven/pytest commands
in disposable isolated containers. Workflow scheduling remains pending.
Offline SDK and real runner tests pass; a live API run has not been verified.

## Repository layout

```text
apps/
  url-shortener/       Java 21 / Spring Boot 3.x / Maven Wrapper
  orchestrator/       Python 3.12 / FastAPI / uv
docs/                 Assignment, specification, plan evidence and architecture decisions
scenarios/            Preserved greenfield, brownfield and ambiguous seed locations
workspaces/           Generated workflow contents (ignored except .gitkeep)
scripts/              Bootstrap verification and ephemeral database fixture
```

Spring Boot owns the URL product. FastAPI will own workflow state and governance.
Agents will return structured results and will never directly change workflow state.
The two services have separate build configurations and migration ownership.
See [the implementation plan](IMPLEMENTATION_PLAN.md),
[specification](docs/IMPLEMENTATION_SPEC.md) and
[service-boundary decision](docs/decisions/ADR-001-service-boundaries.md).

## Prerequisites

- JDK 21 (the build rejects other major versions).
- Python 3.12.13 and uv 0.11.8; uv can download the pinned Python version.
- Docker with Compose v2 for Java Testcontainers tests and database checks.
- GNU Make, a POSIX shell, and network access for the first dependency/image downloads.

Maven 3.9.16 is downloaded by the checked-in Apache Maven Wrapper 3.3.4 and
verified against a pinned SHA-256. Spring Boot 3.5.16 manages Java dependency and
plugin versions. Python dependencies and development tools are exactly pinned
and resolved in `apps/orchestrator/uv.lock`. Formatting uses pinned Spotless with
Google Java Format's four-space AOSP style and Ruff for Python.

On macOS, select the installed Java 21 before running builds:

```sh
export JAVA_HOME=$(/usr/libexec/java_home -v 21)
```

## Verification

From the repository root:

```sh
make bootstrap
make structure
make compose-config
make lint
make test
make build
make test-db
```

`make test` runs the Java unit and PostgreSQL Testcontainers tests, plus the
FastAPI service tests. `make test-db` starts a disposable,
loopback-only PostgreSQL fixture, tests migration, session transactions and
health, and removes the container and its anonymous volume. It fails if Docker is
unavailable; it does not silently skip the database check.

## Run the URL service

Create `.env` from `.env.example`, replace the URL database password, and start
the two development databases with `make up`. The Spring Boot process needs the
same `URL_DB_PASSWORD` value in its environment. Its default JDBC URL points to
the URL database at `localhost:5433`; `URL_DB_JDBC_URL` overrides it.

```sh
cd apps/url-shortener
URL_DB_PASSWORD='the-local-url-database-password' ./mvnw spring-boot:run
```

The Phase 4 HTTP contract is:

| Method | Path | Result |
|---|---|---|
| POST | `/api/v1/links` | JSON with required `url` and optional `customAlias`, `expiresAt`; optional `Idempotency-Key` header → 201 and link metadata |
| GET | `/api/v1/links/{shortCode}` | Metadata or 404 |
| GET | `/api/v1/links/{shortCode}/analytics` | `shortCode`, `totalClicks`, UTC `clicksByDay` or 404 |
| GET | `/{shortCode}` | 302 with original URL in `Location`; 410 if expired or disabled; 404 if missing |
| DELETE | `/api/v1/links/{shortCode}` | Soft-disable a link, including repeated requests → 204; 404 if missing |

Generated codes are seven Base62 characters. A custom alias must be 3–32
letters, digits, `-` or `_`; `api`, `actuator`, `swagger-ui`, `v3` and `health`
are reserved without regard to case. Aliases themselves are case-sensitive.
Duplicate aliases return 409. Only absolute HTTP/HTTPS URLs with a host and
without embedded credentials are accepted. `expiresAt` must be in the future;
redirects expire at the exact timestamp. Generated-code collisions are retried
up to five total attempts, with database uniqueness as the final guard.

`Idempotency-Key` is scoped to the anonymous caller for now. Repeating the
same key and request returns the original 201 response; reusing a key with a
different request returns 409. Records are retained indefinitely for this
prototype, including across restarts. Without authentication, different
clients sharing a key also share its scope, so callers should use unpredictable
keys. The creation limit is a single bounded in-memory window per service
instance, defaults to 60 requests per minute, returns 429 with `Retry-After`,
and resets on process restart. It does not use client IP or proxy headers.
Configure it with `URL_CREATE_RATE_CAPACITY`
and `URL_CREATE_RATE_WINDOW`. It does not aggregate across instances.

Each valid redirect submits a click event to a bounded background writer. The
event stores link ID, UTC time, the referrer's origin if it is a valid HTTP(S)
URL, a coarse `BOT`/`MOBILE`/`DESKTOP`/`OTHER` category, and the request trace
ID. Paths, queries, raw user-agent strings and client IP addresses are not
stored. The analytics API reads persisted events and groups them by UTC day.
Persistence failures or queue saturation can lose events, but cannot change a
valid redirect. Counts are therefore best-effort and may lag immediately after
a redirect; they are not exactly-once. Events currently have no automatic
retention cleanup. The writer defaults to two threads and a queue of 100;
`URL_ANALYTICS_MAX_THREADS`, `URL_ANALYTICS_QUEUE_CAPACITY` and
`URL_ANALYTICS_ENABLED` configure it. A write transaction and PostgreSQL
statement have a two-second timeout, and connection acquisition has a
three-second timeout by default (`URL_DB_CONNECTION_TIMEOUT_MS`).

OpenAPI is at `http://localhost:8080/v3/api-docs`, Swagger UI at
`http://localhost:8080/swagger-ui.html`. Actuator exposes health, readiness,
metrics and Prometheus at `/actuator/health`, `/actuator/health/readiness`,
`/actuator/metrics` and `/actuator/prometheus`; sensitive endpoints such as
`/actuator/env` remain unavailable. Redirect success, analytics writes,
failures and drops have counters without per-link labels. `URL_BASE_URL`
configures the public short URL; the default is
`http://localhost:8080`.

The FastAPI service can run independently. First configure its
`ORCHESTRATOR_DB_*` environment variables and run its migration explicitly:

```sh
cd apps/orchestrator
uv run --locked alembic upgrade head
uv run --locked uvicorn app.main:app --host 127.0.0.1 --port 8000
```

FastAPI serves `GET /health`, `/docs` and `/openapi.json` on port 8000.
Health returns 200 after a PostgreSQL query or 503 when unavailable. Workflow
APIs remain for later phases.

## Compose skeleton

`docker-compose.yml` provisions **only two development PostgreSQL services**:
`url-db` on loopback port 5433 and `orchestrator-db` on loopback port 5434. Each
has its own database, role and persistent volume. PostgreSQL's initial roles are
development bootstrap administrators; later persistence phases will introduce
appropriate restricted application roles. Application containers, migration
startup and the restricted engineering runner are not part of this skeleton.

```sh
cp .env.example .env
# Replace both example database passwords in .env.
make up
make health
make down
```

`make health` checks databases only. `make down` preserves data. `make demo` and
`make smoke` return a clear nonzero “not implemented yet” message rather
than reporting success. No destructive reset command is provided.

## Verification record and scope

See [TESTING.md](docs/TESTING.md) for actual commands/results and the
[traceability matrix](docs/TRACEABILITY.md) for requirement coverage. Later
phase features remain unimplemented. Do not commit `.env`, credentials, generated
workspaces, caches or transient logs. The assignment PDF is marked Schwab Internal;
this work does not publish the repository or its contents.
