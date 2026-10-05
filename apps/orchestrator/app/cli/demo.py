"""Server-owned scenario demonstration commands."""

from typing import Literal

import typer

from app.cli.client import api_json, runtime_from
from app.cli.rendering import emit, render_workflow

app = typer.Typer(help="Start a packaged demonstration scenario.", no_args_is_help=True)


def _start(context: typer.Context, scenario: Literal["greenfield", "brownfield", "ambiguous"]):
    runtime = runtime_from(context)
    result = api_json(
        runtime,
        "POST",
        "/api/v1/workflows",
        json_body={"scenario": scenario.upper(), "demo": True, "providerMode": "fake"},
    )
    emit(runtime.console, result, render_workflow, json_output=runtime.json_output)


@app.command("greenfield")
def greenfield(context: typer.Context) -> None:
    _start(context, "greenfield")


@app.command("brownfield")
def brownfield(context: typer.Context) -> None:
    _start(context, "brownfield")


@app.command("ambiguous")
def ambiguous(context: typer.Context) -> None:
    _start(context, "ambiguous")
