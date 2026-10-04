# Orchestrator bootstrap

Python 3.12.13, FastAPI, Pydantic, Uvicorn and locked development tools.
Use uv 0.11.8. From this directory:

```sh
uv sync --locked
uv run --locked python -m pytest -m 'not integration'
uv run --locked uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Only the framework OpenAPI/docs routes exist. Database sessions, migrations,
health, workflow state, agents and the terminal CLI belong to later phases.
The PostgreSQL fixture is test infrastructure, not an application database layer.
