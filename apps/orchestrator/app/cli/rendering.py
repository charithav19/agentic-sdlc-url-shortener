"""Rich views for API response documents."""

import json
from typing import Any

from rich.console import Console, Group
from rich.json import JSON
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

STATUS_SYMBOLS = {
    "COMPLETED": "✓",
    "SUCCEEDED": "✓",
    "APPROVED": "✓",
    "RUNNING": "▶",
    "READY": "●",
    "PENDING": "○",
    "BLOCKED": "⊘",
    "WAITING_FOR_APPROVAL": "◷",
    "WAITING_APPROVAL": "◷",
    "WAITING_FOR_CLARIFICATION": "?",
    "RETRY_PENDING": "↻",
    "REPLANNING": "↻",
    "FAILED": "✗",
    "REJECTED": "✗",
    "SAFE_STOPPED": "■",
    "ROLLED_BACK": "↶",
    "STALE": "△",
    "INVALIDATED": "△",
    "CANCELLED": "—",
    "SKIPPED": "—",
}


def emit(console: Console, payload: Any, renderer, *, json_output: bool) -> None:
    if json_output:
        console.print(
            json.dumps(payload, indent=2, default=str),
            markup=False,
            highlight=False,
        )
    else:
        renderer(console, payload)


def render_workflow(console: Console, payload: dict[str, Any]) -> None:
    status = value(payload, "status", "workflowStatus", default="UNKNOWN")
    header = Table.grid(padding=(0, 1))
    header.add_column(style="bold cyan", no_wrap=True)
    header.add_column()
    for label, item in (
        ("Workflow", value(payload, "id", "workflowId", default="—")),
        ("Status", status_text(str(status))),
        ("Scenario", value(payload, "scenario", "scenarioType", default="—")),
        ("Provider", value(payload, "providerMode", "provider_mode", default="—")),
        ("Generation", value(payload, "generation", default="—")),
        ("Last success", value(payload, "lastSuccessfulStage", default="—")),
    ):
        header.add_row(label, item if isinstance(item, Text) else str(item))

    content: list[Any] = [header]
    stages = items(payload, "stages", "stageRuns")
    if stages:
        content.append(stage_table(stages))
    next_action = value(payload, "nextAction", "recommendedHumanAction")
    if next_action:
        content.append(Text(f"Next: {next_action}", style="bold yellow"))
    console.print(Panel(Group(*content), title="Workflow", border_style="cyan"))


def stage_table(stages: list[dict[str, Any]]) -> Table:
    table = Table(title="Stages", expand=True)
    table.add_column("Stage", overflow="fold")
    table.add_column("Status", no_wrap=True)
    table.add_column("Attempt", justify="right")
    table.add_column("Blocked / result", overflow="fold")
    for stage in stages:
        status = str(value(stage, "status", default="UNKNOWN"))
        detail = value(
            stage,
            "blockedReason",
            "errorMessage",
            "recommendedAction",
            default="",
        )
        table.add_row(
            str(value(stage, "name", "stageName", default="—")),
            status_text(status),
            str(value(stage, "attempt", default="—")),
            str(detail),
        )
    return table


def render_graph(console: Console, payload: dict[str, Any]) -> None:
    root = Tree(
        f"[bold cyan]Workflow graph[/bold cyan] "
        f"[dim]{value(payload, 'graphHash', 'version', default='')}[/dim]"
    )
    for stage in items(payload, "stages", "nodes"):
        status = str(value(stage, "status", default="PENDING"))
        node = root.add(
            f"{STATUS_SYMBOLS.get(status, '•')} "
            f"[bold]{value(stage, 'name', 'stageName', default='unknown')}[/bold] "
            f"[{status_style(status)}]{status}[/]"
        )
        dependencies = value(stage, "dependencies", default=[]) or []
        if dependencies:
            node.add("depends on: " + ", ".join(map(str, dependencies)))
    console.print(root)


def render_approvals(console: Console, payload: Any) -> None:
    table = Table(title="Approvals", expand=True)
    table.add_column("Status", no_wrap=True)
    table.add_column("Type", overflow="fold")
    table.add_column("Approval ID", overflow="fold")
    table.add_column("Artifact", overflow="fold")
    table.add_column("Version", justify="right")
    table.add_column("Reason / risk", overflow="fold")
    approvals = collection(payload, "approvals", "items")
    if not approvals and isinstance(payload, dict) and value(payload, "approvalId", "id"):
        approvals = [payload]
    for approval in approvals:
        status = str(value(approval, "status", default="UNKNOWN"))
        table.add_row(
            status_text(status),
            str(value(approval, "approvalType", "type", default="—")),
            str(value(approval, "approvalId", "id", default="—")),
            str(value(approval, "artifactId", default="—")),
            str(value(approval, "artifactVersion", default="—")),
            str(value(approval, "reason", "risk", default="")),
        )
    console.print(table)


def render_artifacts(console: Console, payload: Any) -> None:
    table = Table(title="Artifacts", expand=True)
    table.add_column("Name", overflow="fold")
    table.add_column("Type")
    table.add_column("Version", justify="right")
    table.add_column("Status")
    table.add_column("Artifact ID", overflow="fold")
    for artifact in collection(payload, "artifacts", "items"):
        status = str(value(artifact, "status", default="ACTIVE"))
        table.add_row(
            str(value(artifact, "logicalName", "name", default="—")),
            str(value(artifact, "artifactType", "type", default="—")),
            str(value(artifact, "version", default="—")),
            status_text(status),
            str(value(artifact, "artifactId", "id", default="—")),
        )
    console.print(table)


def render_artifact(console: Console, payload: dict[str, Any]) -> None:
    title = (
        f"{value(payload, 'logicalName', 'name', default='Artifact')} "
        f"v{value(payload, 'version', default='?')}"
    )
    metadata = Table.grid(padding=(0, 1))
    metadata.add_column(style="bold cyan")
    metadata.add_column(overflow="fold")
    for label, key_names in (
        ("ID", ("artifactId", "id")),
        ("Type", ("artifactType", "type")),
        ("Status", ("status",)),
        ("SHA-256", ("sha256", "contentSha256")),
        ("Created", ("createdAt",)),
    ):
        metadata.add_row(label, str(value(payload, *key_names, default="—")))
    content = value(payload, "content", default={})
    console.print(Panel(Group(metadata, JSON(json.dumps(content, default=str))), title=title))


def render_lineage(console: Console, payload: Any) -> None:
    root = Tree("[bold cyan]Artifact lineage[/bold cyan]")
    nodes = collection(payload, "nodes", "artifacts", "items")
    labels = {
        str(value(node, "artifactId", "id", default="")): (
            f"{value(node, 'logicalName', 'name', default='artifact')} "
            f"v{value(node, 'version', default='?')}"
        )
        for node in nodes
    }
    edges = collection(payload, "edges", "lineage")
    if edges:
        for edge in edges:
            parent = str(value(edge, "parentArtifactId", "parentId", default="?"))
            child = str(value(edge, "childArtifactId", "childId", default="?"))
            relation = value(edge, "relationship", default="DERIVED_FROM")
            branch = root.add(labels.get(parent, parent))
            branch.add(f"{relation} → {labels.get(child, child)}")
    else:
        for node in nodes:
            root.add(labels.get(str(value(node, "artifactId", "id", default="")), "artifact"))
    console.print(root)


def render_clarifications(console: Console, payload: Any) -> None:
    table = Table(title="Clarifications", expand=True)
    table.add_column("Status", no_wrap=True)
    table.add_column("Question ID", overflow="fold")
    table.add_column("Question", overflow="fold")
    table.add_column("Answer", overflow="fold")
    for item in collection(payload, "clarifications", "questions", "items"):
        status = str(value(item, "status", default="PENDING"))
        table.add_row(
            status_text(status),
            str(value(item, "questionId", "id", default="—")),
            str(value(item, "question", default="—")),
            str(value(item, "answer", default="")),
        )
    console.print(table)


def render_audit(console: Console, payload: Any) -> None:
    table = Table(title="Audit timeline", expand=True)
    table.add_column("Seq", justify="right")
    table.add_column("Time", no_wrap=True)
    table.add_column("Event", overflow="fold")
    table.add_column("Actor", overflow="fold")
    table.add_column("State / reason", overflow="fold")
    for event in collection(payload, "events", "items"):
        before = value(event, "beforeState", default="")
        after = value(event, "afterState", default="")
        transition = f"{before} → {after}" if before or after else ""
        reason = value(event, "reason", default="")
        table.add_row(
            str(value(event, "sequence", default="—")),
            str(value(event, "occurredAt", "timestamp", default="—")),
            str(value(event, "eventType", "type", default="—")),
            str(value(event, "actorId", default="—")),
            " · ".join(item for item in (transition, str(reason)) if item),
        )
    console.print(table)


def render_metrics(console: Console, text: str) -> None:
    table = Table(title="Orchestration metrics", expand=True)
    table.add_column("Metric", overflow="fold")
    table.add_column("Value", justify="right")
    for line in text.splitlines():
        if not line or line.startswith("#") or "{" in line:
            continue
        name, _, metric_value = line.partition(" ")
        if not metric_value:
            continue
        table.add_row(name, metric_value)
    console.print(table)


def render_result_panel(console: Console, payload: dict[str, Any], title: str) -> None:
    status = value(payload, "status", "workflowStatus", default="accepted")
    body = Table.grid(padding=(0, 1))
    body.add_column(style="bold cyan")
    body.add_column(overflow="fold")
    for key, item in payload.items():
        if isinstance(item, (dict, list)):
            continue
        body.add_row(_humanize(key), str(item))
    console.print(Panel(body, title=f"{STATUS_SYMBOLS.get(str(status), '✓')} {title}"))


def collection(payload: Any, *keys: str) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in keys:
            candidate = payload.get(key)
            if isinstance(candidate, list):
                return [item for item in candidate if isinstance(item, dict)]
    return []


def items(payload: dict[str, Any], *keys: str) -> list[dict[str, Any]]:
    return collection(payload, *keys)


def value(payload: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in payload and payload[key] is not None:
            return payload[key]
    return default


def status_text(status: str) -> Text:
    return Text(f"{STATUS_SYMBOLS.get(status, '•')} {status}", style=status_style(status))


def status_style(status: str) -> str:
    if status in {"COMPLETED", "SUCCEEDED", "APPROVED", "ACTIVE"}:
        return "bold green"
    if status in {"FAILED", "REJECTED", "SAFE_STOPPED"}:
        return "bold red"
    if status in {"RUNNING", "READY"}:
        return "bold cyan"
    if status.startswith("WAITING") or status in {"BLOCKED", "RETRY_PENDING"}:
        return "bold yellow"
    return "dim"


def _humanize(value: str) -> str:
    return " ".join(part.capitalize() for part in value.replace("_", " ").split())
