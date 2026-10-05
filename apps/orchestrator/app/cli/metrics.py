"""Reliability metrics CLI command."""

import json

import typer

from app.cli.client import api_text, runtime_from
from app.cli.rendering import render_metrics


def show_metrics(context: typer.Context) -> None:
    runtime = runtime_from(context)
    result = api_text(runtime, "GET", "/metrics")
    if runtime.json_output:
        runtime.console.print(
            json.dumps(_scalar_metrics(result), indent=2),
            markup=False,
            highlight=False,
        )
    else:
        render_metrics(runtime.console, result)


def _scalar_metrics(document: str) -> dict[str, float | None]:
    values: dict[str, float | None] = {}
    for line in document.splitlines():
        if not line or line.startswith("#") or "{" in line:
            continue
        name, separator, raw = line.partition(" ")
        if not separator:
            continue
        values[name] = None if raw == "NaN" else float(raw)
    return values
