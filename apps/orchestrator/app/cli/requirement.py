"""Requirement update CLI command."""

import uuid
from pathlib import Path
from typing import Annotated

import typer

from app.cli.client import api_json, fail, runtime_from
from app.cli.rendering import emit, render_result_panel

app = typer.Typer(help="Version workflow requirements.", no_args_is_help=True)


@app.command("update")
def update_requirement(
    context: typer.Context,
    workflow_id: uuid.UUID,
    file: Annotated[
        Path | None, typer.Option("--file", exists=True, dir_okay=False, readable=True)
    ] = None,
    requirement: Annotated[str | None, typer.Option("--requirement")] = None,
    workflow_version: Annotated[int | None, typer.Option("--workflow-version", min=1)] = None,
    reason: Annotated[str | None, typer.Option("--reason")] = None,
) -> None:
    runtime = runtime_from(context)
    if (file is None) == (requirement is None):
        fail(runtime.console, "Provide exactly one of --file or --requirement")
    requirement_text = file.read_text(encoding="utf-8") if file else requirement or ""
    body = {
        "requirement": requirement_text,
        "updateId": str(uuid.uuid4()),
        "expectedWorkflowVersion": workflow_version,
        "reason": reason,
    }
    result = api_json(
        runtime,
        "POST",
        f"/api/v1/workflows/{workflow_id}/requirements",
        json_body={key: item for key, item in body.items() if item is not None},
        reviewer=True,
    )
    emit(
        runtime.console,
        result,
        lambda console, payload: render_result_panel(console, payload, "Requirement updated"),
        json_output=runtime.json_output,
    )
