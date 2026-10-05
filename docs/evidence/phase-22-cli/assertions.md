# Phase 22 CLI assertions

- `agentic` is installed through `[project.scripts]` and uses the pinned Typer,
  Rich, and runtime `httpx` dependencies.
- Command handlers call FastAPI paths and contain no database sessions,
  repositories, workflow transitions, gate decisions, or policy decisions.
- Workflow status uses a Rich panel and stage table; graph and lineage use
  trees; approval, artifact, clarification, audit, and metrics use tables.
- Approval submission shows the exact pending artifact version and requires a
  user confirmation unless `--yes` is explicitly supplied.
- Mutating human requests place the local reviewer token and actor ID in HTTP
  headers. Tests use a fake token and verify it is never rendered.
- Watch polling stops at terminal or human-attention states, is bounded by
  `--max-polls`, and never invokes cancellation.
- `--json`, `--no-color`, structured error exit codes, audit pagination, and
  narrow Rich output are presentation concerns only.
- Demo commands ask the workflow API to select a packaged scenario. The CLI
  contains no fabricated scenario result; scenario packages remain later work.
