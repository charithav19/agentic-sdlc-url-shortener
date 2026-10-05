"""Workflow CLI commands."""

import json
import time
import uuid
from pathlib import Path
from typing import Annotated

import typer

from app.cli.client import api_json, fail, runtime_from
from app.cli.rendering import emit, render_graph, render_workflow, value

app = typer.Typer(help="Create and inspect workflow runs.", no_args_is_help=True)
ATTENTION_STATUSES = {
    "COMPLETED",
    "FAILED",
    "CANCELLED",
    "SAFE_STOPPED",
    "WAITING_FOR_APPROVAL",
    "WAITING_FOR_CLARIFICATION",
}


@app.command("create")
def create_workflow(
    context: typer.Context,
    scenario: Annotated[
        str, typer.Option("--scenario", help="greenfield, brownfield, or ambiguous")
    ],
    requirement_file: Annotated[
        Path | None,
        typer.Option("--requirement-file", exists=True, dir_okay=False, readable=True),
    ] = None,
    requirement: Annotated[str | None, typer.Option("--requirement")] = None,
    seed_ref: Annotated[str | None, typer.Option("--seed-ref")] = None,
    provider: Annotated[str, typer.Option("--provider")] = "fake",
) -> None:
    """Create a workflow and return immediately with its reference."""

    runtime = runtime_from(context)
    if (requirement_file is None) == (requirement is None):
        fail(runtime.console, "Provide exactly one of --requirement-file or --requirement")
    requirement_text = (
        requirement_file.read_text(encoding="utf-8") if requirement_file else requirement or ""
    )
    payload = {
        "scenario": scenario.upper(),
        "requirement": requirement_text,
        "providerMode": provider,
    }
    if seed_ref:
        payload["seedRef"] = seed_ref
    result = api_json(runtime, "POST", "/api/v1/workflows", json_body=payload)
    emit(runtime.console, result, render_workflow, json_output=runtime.json_output)


@app.command("status")
def workflow_status(context: typer.Context, workflow_id: uuid.UUID) -> None:
    """Show workflow state, stages, blockers, and the next action."""

    runtime = runtime_from(context)
    result = api_json(runtime, "GET", f"/api/v1/workflows/{workflow_id}")
    emit(runtime.console, result, render_workflow, json_output=runtime.json_output)


@app.command("watch")
def watch_workflow(
    context: typer.Context,
    workflow_id: uuid.UUID,
    interval: Annotated[float, typer.Option(min=0.1, max=60.0)] = 2.0,
    max_polls: Annotated[int, typer.Option(min=1, max=10_000)] = 300,
) -> None:
    """Poll until the workflow terminates or needs human attention."""

    runtime = runtime_from(context)
    last_version: object = None
    try:
        for poll in range(max_polls):
            result = api_json(runtime, "GET", f"/api/v1/workflows/{workflow_id}")
            version = value(result, "stateVersion", "version", "workflowVersion")
            if runtime.json_output:
                runtime.console.print(
                    json.dumps(result, separators=(",", ":"), default=str),
                    markup=False,
                    highlight=False,
                    soft_wrap=True,
                )
            elif poll == 0 or version != last_version:
                render_workflow(runtime.console, result)
            last_version = version
            status = str(value(result, "status", "workflowStatus", default="UNKNOWN"))
            if status in ATTENTION_STATUSES:
                return
            if poll + 1 < max_polls:
                time.sleep(interval)
    except KeyboardInterrupt:
        runtime.console.print("[yellow]Watch stopped; workflow remains running.[/yellow]")
        raise typer.Exit(130) from None
    fail(runtime.console, f"Watch reached the {max_polls}-poll limit", code=6)


@app.command("graph")
def workflow_graph(context: typer.Context, workflow_id: uuid.UUID) -> None:
    """Show the versioned DAG and current stage states."""

    runtime = runtime_from(context)
    result = api_json(runtime, "GET", f"/api/v1/workflows/{workflow_id}/graph")
    emit(runtime.console, result, render_graph, json_output=runtime.json_output)
