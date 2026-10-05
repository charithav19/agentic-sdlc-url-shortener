"""Typer entry point for the agentic SDLC orchestrator."""

import os
import uuid
from typing import Annotated

import typer
from rich.console import Console

from app.cli import approval, artifact, clarification, demo, requirement, workflow
from app.cli.audit import show_audit
from app.cli.client import CliConfigError, CliRuntime, fail, make_api_client
from app.cli.metrics import show_metrics

app = typer.Typer(
    name="agentic",
    help="Inspect and govern Agentic SDLC workflows through FastAPI.",
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)
app.add_typer(workflow.app, name="workflow")
app.add_typer(approval.app, name="approval")
app.add_typer(artifact.app, name="artifact")
app.add_typer(clarification.app, name="clarification")
app.add_typer(requirement.app, name="requirement")
app.add_typer(demo.app, name="demo")


@app.callback()
def initialize(
    context: typer.Context,
    base_url: Annotated[
        str | None,
        typer.Option("--base-url", envvar="ORCHESTRATOR_BASE_URL", help="FastAPI base URL."),
    ] = None,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit machine-readable JSON where available.")
    ] = False,
    no_color: Annotated[
        bool, typer.Option("--no-color", help="Disable ANSI color output.")
    ] = False,
) -> None:
    """Configure the HTTP client shared by this invocation."""

    console = Console(no_color=no_color)
    try:
        client = make_api_client(
            base_url or os.getenv("ORCHESTRATOR_BASE_URL", "http://127.0.0.1:8000")
        )
    except CliConfigError as error:
        fail(console, str(error))
    context.obj = CliRuntime(client=client, console=console, json_output=json_output)
    context.call_on_close(client.close)


@app.command("lineage")
def lineage(context: typer.Context, workflow_id: uuid.UUID) -> None:
    """Display artifact relationships as a tree."""

    artifact.show_lineage(context, workflow_id)


@app.command("audit")
def audit(
    context: typer.Context,
    workflow_id: uuid.UUID,
    after_sequence: Annotated[int, typer.Option("--after-sequence", min=0)] = 0,
    limit: Annotated[int, typer.Option(min=1, max=500)] = 100,
) -> None:
    """Display a chronological workflow audit page."""

    show_audit(context, workflow_id, after_sequence, limit)


@app.command("metrics")
def metrics(context: typer.Context) -> None:
    """Display low-cardinality orchestration reliability metrics."""

    show_metrics(context)


def run() -> None:
    app()


if __name__ == "__main__":
    run()
