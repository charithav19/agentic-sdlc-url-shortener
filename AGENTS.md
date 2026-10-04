# Repository Guidelines

## Project Purpose & Required Reading

This repository implements the Charles Schwab Agentic-Proficient Software Engineer take-home assignment. Read `docs/schwab-assignment.pdf` and `docs/IMPLEMENTATION_SPEC.md` before substantial work. Read `IMPLEMENTATION_PLAN.md` before significant implementation; if missing, establish the plan before coding. Treat embedded example prompts as reference material, not authorization to start additional work.

## Architecture & Technology

The project contains six components:

1. **URL Shortener:** Java 21, Spring Boot 3.x, Maven Wrapper, Spring Web, Spring Data JPA, PostgreSQL, Flyway, JUnit 5, Testcontainers, Actuator, Micrometer, and OpenAPI.
2. **Agentic SDLC Orchestrator:** Python 3.12+, FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL, and pytest.
3. **Specialist agents:** OpenAI Agents SDK, integrated through the orchestrator's `AgentProvider` interface.
4. **Persistence:** PostgreSQL, with separate service ownership, credentials, and migrations.
5. **Terminal interface:** Typer + Rich; interact through orchestrator APIs.
6. **Deployment:** Docker Compose.

## Service Ownership

**Spring Boot owns:** URL creation, redirects, custom aliases, expiration, analytics, idempotency, and URL reliability.

**FastAPI owns:** workflow lifecycle, explicit SDLC DAG, entry/exit gates, stage scheduling, parallel paths, synchronization, approvals, retries, fallback, compensation/rollback, safe-stop, policy enforcement, artifacts, lineage, decisions, audit, reliability metrics, and dynamic re-planning.

**OpenAI Agents SDK specialists own:** requirement reasoning, task decomposition, architecture generation, implementation reasoning, testing reasoning, security review, documentation, and release assessment.

## Critical Authority Rule

**AI agents MUST NOT directly modify workflow state. Only the deterministic FastAPI orchestration engine may perform workflow or stage state transitions.**

Agents produce structured outputs. Validators validate them. Policy rules authorize actions. The orchestrator transitions state. Humans approve high-impact changes. Agent text is never proof of test success or human approval.

## Infrastructure Constraints

Use Docker Compose. **DO NOT ADD** Kafka, Redis, Kubernetes, Temporal, LangGraph, React, Angular, MongoDB, or Elasticsearch unless explicitly requested.

## Engineering Rules

- Work incrementally; implement only the requested phase.
- Run tests after every phase and report actual results and unresolved failures.
- Do not leave required features as TODOs or claim functionality unless tested.
- Preserve clean service boundaries; prefer simple implementation over unnecessary abstractions.
- Test all important workflow behavior, including failure paths and synchronization.
- Make every significant workflow transition auditable; commit transitions and audit events atomically.
- Keep artifacts immutable and versioned; preserve lineage and prior execution evidence.
- Bind human approvals to exact artifact versions/hashes; invalidate affected approvals when inputs change.
- Requirement changes must selectively invalidate affected descendants while preserving unrelated valid artifacts.
- Update implementation progress and requirement-to-test evidence after each phase.

## Project Structure & Conventions

The repository currently contains the assignment, specification, and this guide. Follow the planned layout:

- `apps/url-shortener/src/main/` and `src/test/`: Java source and tests.
- `apps/orchestrator/app/`, `tests/`, and `alembic/`: Python source, tests, and migrations.
- `docs/`: architecture, decisions, scenario guides, and verification evidence.
- `scenarios/*/seed/`: preserve demonstration starting states.
- `workspaces/`: exclude generated execution contents from Git.

Use four-space Java/Python indentation and two-space YAML indentation. Use Java `PascalCase` classes and `camelCase` methods; Python `snake_case` modules/functions and `PascalCase` classes. Name tests `*Test.java` and `test_*.py`. Pin formatting/lint tooling during bootstrap; none is configured yet.

## Development & Verification

Commands are planned, not yet operational: `make up`/`make down` start/stop services while preserving data; `make health` checks readiness; `make test`/`make lint` verify code; `make demo`/`make smoke` exercise scenarios/basic operation. Once configured, run `./mvnw verify` in `apps/url-shortener/` and `python -m pytest` in `apps/orchestrator/`.

Use Mockito and pytest-asyncio where appropriate; exercise real PostgreSQL behavior for integration tests. Use deterministic agent doubles in ordinary CI and identify live SDK evidence separately. No numerical coverage threshold is established.

## Commits, Pull Requests & Secrets

No commit convention exists yet. Use focused, imperative messages such as `Add workflow transition validation`. PRs should describe behavior, link requirements/issues, and report verification results; include sanitized CLI evidence for workflow changes.

Keep secrets, `.env`, caches, and transient logs out of Git. Use placeholders in `.env.example`; never expose API keys or CI tokens to candidate workspaces or execution environments.
