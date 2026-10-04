# ADR-001: Separate product and orchestration services

Status: accepted for the Phase 1 bootstrap.

The Spring Boot application under `apps/url-shortener` owns URL behavior and its
future Flyway migrations. The FastAPI package under `apps/orchestrator` owns
workflow state, approvals, policy and its future Alembic migrations. Each service
has an independent build and a separately owned PostgreSQL database and role.
The bootstrap Compose file uses separate PostgreSQL containers/volumes, avoiding
shared schema access or database-initialization scripts in this phase.

The deterministic FastAPI engine will be the only workflow-state writer.
OpenAI Agents SDK integration, specialist tools and Typer/Rich CLI belong to
later phases. No agent runtime or business database layer is included now.

Alternatives considered: one mixed service or shared database schema reduces
initial setup but blurs ownership and migration authority. Extra infrastructure
and a web frontend add no value to this phase and are prohibited by the contract.

Consequences: two dependency/build toolchains and local database instances;
clear independent ownership, test boundaries and migration histories. Initial
PostgreSQL users are local development bootstrap administrators, not a claim of
production least privilege. Restricted service roles will be introduced with
the persistence implementations. Phase 26 completes application packaging.

Version references: [Spring Boot 3.5 requirements](https://docs.spring.io/spring-boot/3.5/system-requirements.html),
[Apache Maven Wrapper](https://maven.apache.org/tools/wrapper/index.html),
[uv locking and syncing](https://docs.astral.sh/uv/concepts/projects/sync/),
[Compose application model](https://docs.docker.com/compose/intro/compose-application-model/).
