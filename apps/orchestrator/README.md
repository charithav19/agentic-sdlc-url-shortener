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
`/docs` and `/openapi.json` describe the application routes. Request
responses have `X-Trace-Id`; errors include the same identifier without
database credentials.

From the repository root, `make test-db` runs PostgreSQL integration tests
against a disposable database. Phase 6 adds UUID-keyed workflow/stage records,
immutable artifact versions, lineage, decisions, exact-version approval
requests and append-only audit events. The `0002_workflow_foundation`
migration adds database constraints and mutation-rejecting triggers. Internal
repositories and the creation service write provenance and audit events in one
transaction. Workflow execution routes and terminal commands remain pending;
the later phase additions below provide internal state and agent interfaces.

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

## Phase 10–11 agent runtime

`app.agents.settings.create_agent_provider()` returns the primary
`OpenAIAgentProvider` by default. Export `OPENAI_MODEL` and
`OPENAI_API_KEY` in the trusted process environment; missing configuration
fails explicitly. The adapter uses pinned `openai-agents==0.23.1`,
`Agent(output_type=...)`, `Runner.run(max_turns=...)`, a 60-second deadline,
an 8192 output-token ceiling, no client retries, and no exported SDK traces.

The internal invocation contract is:

```python
from app.agents.requirement import RequirementAgent
from app.agents.settings import create_agent_provider

# context is an AgentContext with UUIDs, generation/attempt, requirement,
# versioned snapshots and an explicitly authorized tool subset.
result = await create_agent_provider().run(RequirementAgent(), context)
normalized = result.output.normalized_requirement
```

All eight specialists are bound to existing graph executor names in
`app.agents.registry.SPECIALISTS`. They return strict Pydantic outputs.
Result metadata includes provider/model/SDK, instruction/schema/context
hashes, workflow/stage/trace IDs, generation, attempt and execution budgets.
The result envelope is returned to the caller; it is not yet persisted by a
scheduler.

Tests use the `agent_provider` fixture, a `FakeAgentProvider` with explicit
responses. Application callers can select `AGENT_PROVIDER=fake` and supply
`fake_outputs` to the factory. Missing fixtures fail; real failures never
fall back to fake output.

The SDK exposes bounded engineering tools over `workspaces/<workflow-UUID>/`.
Per-specialist allowlists and per-run grants determine which tools are exposed.
Implementation can write/patch/build/test, testing can write/patch/test, and
documentation can write/patch. Requirement/release agents remain artifact-only.
No tool accesses a database, changes workflow status or grants approval.
Provider results attach file/command receipts created by the trusted tools.

The seven engineering tools are `list_files()`, `read_file(path)`,
`search_code(text)`, `write_file(path, content)`,
`apply_patch(path, old_text, new_text)`, `run_build(command, project)` and
`run_tests(command, project)`. Patches require a unique exact match.
`project` is a workspace-relative directory or `.`; commands must exactly
match `mvn package` for builds, or `mvn test`/`pytest` for tests.
There is no arbitrary shell or extra-argument interface.

The creation service allocates the UUID directory. The SDK provider derives
workspace ownership from context, never from a model-supplied root. Existing
`workspace_ref` values are not used to authorize paths. Traversal, other
workspaces, secrets, symlinks, hardlinks and sockets are denied.

Prepare and verify the trusted runner from the repository root:

```sh
make runner-image
make test-runner
```

Docker must be available. Building the image downloads trusted dependencies;
candidate runs are offline. The image supplies Java 21/Maven, Python/pytest
and a small Maven cache; projects needing other dependencies require a trusted
image rebuild. Runs receive only a bounded file archive, no host mounts,
network or credentials. Build output is ephemeral; receipts record actual
exit codes, hashes, timestamps and failures. See [SECURITY.md](../../docs/SECURITY.md)
for file/command limits and the tested isolation boundary.

Ordinary offline verification and the explicitly paid live smoke:

```sh
uv run --locked python -m pytest -m 'not integration'
# Requires exported OPENAI_MODEL and OPENAI_API_KEY; synthetic input only.
RUN_LIVE_AGENT_TESTS=1 uv run --locked python -m pytest tests/live/test_sdk_smoke.py -q
```

The offline SDK tests execute the real Runner against a local model stub.
They do not establish live API connectivity or model quality.

## Phase 13 approval checkpoints

`POST /api/v1/workflows/{workflow_id}/approvals` submits an `APPROVED` or
`REJECTED` decision for an existing pending checkpoint. The request includes
`approvalId`, exact `artifactId` and `artifactVersion`, `workflowVersion`, and
an optional reason; rejection requires a reason. Supply
`Authorization: Bearer <ORCHESTRATOR_LOCAL_REVIEWER_TOKEN>` and an explicit
`X-Reviewer-Id`. The local token is a prototype credential for a trusted local
reviewer process and must not be exposed to agents or candidate workspaces.

The orchestrator pauses a running workflow when it requests architecture,
high-impact-change, assumption, or release approval. Approval resumes only when
no other checkpoint is pending. Rejection leaves the workflow waiting. A new
version of the same logical artifact invalidates its older pending or approved
decisions. Completion additionally requires a current exact-version `RELEASE`
approval. Approval request, decision/invalidation, and workflow state events are
committed atomically where they occur.

## Phases 14–15 scheduler and joins

`WorkflowScheduler.run_cycle(workflow_id)` recomputes current-generation DAG
readiness, runs the stages ready at cycle start with bounded `asyncio`
concurrency, then recomputes mandatory fan-in joins. Construct it with
`WorkflowScheduler.configured(...)` to use
`ORCHESTRATOR_MAX_PARALLEL_STAGES` (default three) and
`ORCHESTRATOR_STAGE_CLAIM_LEASE_SECONDS` (default 300).

Each worker first obtains an exclusive PostgreSQL claim. The claim atomically
changes `READY → RUNNING`, stores an owner, UUID token and expiry, and appends an
audit event. Only the same unexpired token in the current workflow generation
can commit `SUCCEEDED` or `FAILED`. The database also prevents two active claims
for the same stage/generation.

The configured DAG provides both parallel groups: implementation/test-design/
documentation-draft after architecture approval, and unit/integration/security
validation after build. Build remains blocked until both implementation and test
design succeed. This phase does not reclaim expired/uncertain claims or assemble
parallel workspace overlays; those paths remain disabled pending later recovery
and candidate-assembly work.
