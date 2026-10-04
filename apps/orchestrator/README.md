# Orchestrator foundation

Python 3.12.13, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, Pydantic,
OpenAI Agents SDK, Typer, Rich, and locked development tools. Use uv 0.11.8.
From this directory:

```sh
uv sync --locked
uv run --locked python -m pytest -m 'not integration'
uv run --locked alembic upgrade head
uv run --locked uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Set `ORCHESTRATOR_DB_HOST`, `ORCHESTRATOR_DB_PORT`,
`ORCHESTRATOR_DB_NAME`, `ORCHESTRATOR_DB_USER`, and
`ORCHESTRATOR_DB_PASSWORD` in the process environment. The root
`.env.example` documents local values. Migrations are an explicit operator
step; application startup does not alter the schema. `GET /health` executes a
PostgreSQL probe and returns 200 when reachable or 503 when unavailable.
`/docs` and `/openapi.json` describe the sole application route. Request
responses have `X-Trace-Id`; errors include the same identifier without
database credentials.

From the repository root, `make test-db` runs PostgreSQL integration tests
against a disposable database. Phase 6 adds UUID-keyed workflow/stage records,
immutable artifact versions, lineage, decisions, exact-version approval
requests and append-only audit events. The `0002_workflow_foundation`
migration adds database constraints and mutation-rejecting triggers. Internal
repositories and the creation service write provenance and audit events in one
transaction. There are no workflow execution routes, stage transitions,
agent execution or terminal commands yet.

Phase 7 adds `config/default_sdlc.yaml` and the pure graph loader. The
ordinary DAG has 16 stages; `load_graph(blocking_ambiguity=True)` inserts
`CLARIFICATION` after requirement analysis and makes task decomposition
depend on it. The loader rejects missing dependencies, duplicate names,
cycles, unknown symbolic executors/gates and invalid retry policies. Each
variant has a deterministic hash. The YAML is included in the wheel.
Symbolic executors and gates are declarations only; no stage is executed.

Phase 8 adds `StageDependencyResolver`. Given the graph and current stage
snapshots, it returns deterministic `READY`/`BLOCKED` decisions and unmet
dependency names. Only `SUCCEEDED` from the current generation releases a
child. It does not change persisted stage state, evaluate gates or run agents.

Phase 9 adds `WorkflowOrchestrator`, the only application authority permitted
to change workflow or stage status. It checks explicit legal transition
tables, locks and version-checks records, then commits the status update and
audit event atomically. Direct ORM status mutation is rejected. This is a
state-control foundation; it does not schedule stages or invoke agents.
