"""Audit timeline CLI command."""

import uuid
from typing import Annotated

import typer

from app.cli.client import api_json, runtime_from
from app.cli.rendering import emit, render_audit


def show_audit(
    context: typer.Context,
    workflow_id: uuid.UUID,
    after_sequence: Annotated[int, typer.Option("--after-sequence", min=0)] = 0,
    limit: Annotated[int, typer.Option(min=1, max=500)] = 100,
) -> None:
    runtime = runtime_from(context)
    result = api_json(
        runtime,
        "GET",
        f"/api/v1/workflows/{workflow_id}/audit",
        params={"afterSequence": after_sequence, "limit": limit},
    )
    emit(runtime.console, result, render_audit, json_output=runtime.json_output)
