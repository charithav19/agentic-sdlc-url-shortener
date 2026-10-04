# Schwab Agentic Engineering

Monorepo for a Spring Boot URL shortener and a deterministic FastAPI SDLC
orchestrator. **Phase 1 bootstrap only:** both applications have buildable shells;
business endpoints, workflow execution and agent integrations are not implemented.

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
The two services have separate build configurations and future migration ownership.
See [the implementation plan](IMPLEMENTATION_PLAN.md),
[specification](docs/IMPLEMENTATION_SPEC.md) and
[service-boundary decision](docs/decisions/ADR-001-service-boundaries.md).

## Prerequisites

- JDK 21 (the build rejects other major versions).
- Python 3.12.13 and uv 0.11.8; uv can download the pinned Python version.
- Docker with Compose v2 for database checks. Unit bootstrap tests do not need Docker.
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

## Bootstrap verification

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

`make test` runs only bootstrap checks. `make test-db` starts a disposable,
loopback-only PostgreSQL fixture, executes `SELECT 1` through the Python driver,
and removes the container and its anonymous volume. It fails if Docker is
unavailable; it does not silently skip the database check.

## Run the application shells

```sh
cd apps/url-shortener
./mvnw spring-boot:run
```

In another terminal, from the repository root:

```sh
cd apps/orchestrator
uv run --locked uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The Java shell starts on port 8080 and has no product endpoints. FastAPI provides
framework documentation at `http://127.0.0.1:8000/docs` and an empty OpenAPI paths
map; health and workflow APIs arrive in later phases. OpenAI credentials are not
needed or consumed during bootstrap.

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
`make smoke` return a clear nonzero “not implemented in Phase 1” message rather
than reporting success. No destructive reset command is provided.

## Verification record and scope

See [TESTING.md](docs/TESTING.md) for actual commands/results and the
[traceability matrix](docs/TRACEABILITY.md) for requirement coverage. Later
phase features remain unimplemented. Do not commit `.env`, credentials, generated
workspaces, caches or transient logs. The assignment PDF is marked Schwab Internal;
this bootstrap does not publish the repository or its contents.
