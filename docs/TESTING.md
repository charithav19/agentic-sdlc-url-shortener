# Testing and verification

## Phase 1 — verified on 2026-10-04

Verification ran from the actual repository after the bootstrap files were installed.
No product endpoints, persistence models, workflow engine, agents, migrations or
scenario functionality are implemented. The tests verify only the application
shells, build configuration and database test infrastructure.

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
