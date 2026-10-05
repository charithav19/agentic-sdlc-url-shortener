"""Artifact inventory and lineage CLI commands."""

import uuid
from typing import Annotated, Any

import typer

from app.cli.client import CliRuntime, api_json, fail, runtime_from
from app.cli.rendering import (
    collection,
    emit,
    render_artifact,
    render_artifacts,
    render_lineage,
    value,
)

app = typer.Typer(help="Inspect immutable workflow artifacts.", no_args_is_help=True)


@app.command("list")
def list_artifacts(context: typer.Context, workflow_id: uuid.UUID) -> None:
    runtime = runtime_from(context)
    result = api_json(runtime, "GET", f"/api/v1/workflows/{workflow_id}/artifacts")
    emit(runtime.console, result, render_artifacts, json_output=runtime.json_output)


@app.command("show")
def show_artifact(
    context: typer.Context,
    workflow_id: uuid.UUID,
    artifact_id: Annotated[uuid.UUID | None, typer.Argument()] = None,
) -> None:
    runtime = runtime_from(context)
    selected_id = artifact_id or _single_artifact_id(runtime, workflow_id)
    result = api_json(
        runtime,
        "GET",
        f"/api/v1/workflows/{workflow_id}/artifacts/{selected_id}",
    )
    emit(runtime.console, result, render_artifact, json_output=runtime.json_output)


def show_lineage(context: typer.Context, workflow_id: uuid.UUID) -> None:
    runtime = runtime_from(context)
    result = api_json(runtime, "GET", f"/api/v1/workflows/{workflow_id}/lineage")
    emit(runtime.console, result, render_lineage, json_output=runtime.json_output)


def _single_artifact_id(runtime: CliRuntime, workflow_id: uuid.UUID) -> Any:
    result = api_json(runtime, "GET", f"/api/v1/workflows/{workflow_id}/artifacts")
    artifacts = collection(result, "artifacts", "items")
    if len(artifacts) != 1:
        fail(runtime.console, "Provide ARTIFACT_ID when the workflow does not have one artifact")
    artifact_id = value(artifacts[0], "artifactId", "id")
    if artifact_id is None:
        fail(runtime.console, "The artifact response did not contain an ID")
    return artifact_id
