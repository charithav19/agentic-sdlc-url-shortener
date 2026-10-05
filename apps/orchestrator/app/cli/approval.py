"""Explicit human approval CLI commands."""

import uuid
from typing import Annotated, Any

import typer

from app.cli.client import CliRuntime, api_json, fail, runtime_from
from app.cli.rendering import collection, emit, render_approvals, value

app = typer.Typer(help="Review and decide approval checkpoints.", no_args_is_help=True)


@app.command("list")
def list_approvals(context: typer.Context, workflow_id: uuid.UUID) -> None:
    runtime = runtime_from(context)
    result = _load(runtime, workflow_id)
    emit(runtime.console, result, render_approvals, json_output=runtime.json_output)


@app.command("approve")
def approve(
    context: typer.Context,
    workflow_id: uuid.UUID,
    approval_id: Annotated[uuid.UUID | None, typer.Option("--approval-id")] = None,
    reason: Annotated[str | None, typer.Option("--reason")] = None,
    yes: Annotated[
        bool, typer.Option("--yes", help="Confirm this exact approval decision.")
    ] = False,
) -> None:
    runtime = runtime_from(context)
    source = _load(runtime, workflow_id)
    selected = _select_pending(runtime, source, approval_id)
    render_approvals(runtime.console, [selected])
    if not yes and not typer.confirm("Approve this exact artifact version?", default=False):
        fail(runtime.console, "Approval was not submitted", code=1)
    result = _decide(runtime, workflow_id, source, selected, "APPROVED", reason)
    emit(runtime.console, result, render_approvals, json_output=runtime.json_output)


@app.command("reject")
def reject(
    context: typer.Context,
    workflow_id: uuid.UUID,
    approval_id: Annotated[uuid.UUID | None, typer.Option("--approval-id")] = None,
    reason: Annotated[str | None, typer.Option("--reason")] = None,
    yes: Annotated[bool, typer.Option("--yes", help="Confirm this rejection.")] = False,
) -> None:
    runtime = runtime_from(context)
    source = _load(runtime, workflow_id)
    selected = _select_pending(runtime, source, approval_id)
    render_approvals(runtime.console, [selected])
    rejection_reason = reason or typer.prompt("Rejection reason")
    if not rejection_reason.strip():
        fail(runtime.console, "A rejection reason is required")
    if not yes and not typer.confirm("Reject this exact artifact version?", default=False):
        fail(runtime.console, "Rejection was not submitted", code=1)
    result = _decide(
        runtime,
        workflow_id,
        source,
        selected,
        "REJECTED",
        rejection_reason,
    )
    emit(runtime.console, result, render_approvals, json_output=runtime.json_output)


def _load(runtime: CliRuntime, workflow_id: uuid.UUID) -> Any:
    return api_json(runtime, "GET", f"/api/v1/workflows/{workflow_id}/approvals")


def _select_pending(
    runtime: CliRuntime, payload: Any, approval_id: uuid.UUID | None
) -> dict[str, Any]:
    approvals = collection(payload, "approvals", "items")
    pending = [item for item in approvals if value(item, "status") == "PENDING"]
    if approval_id is not None:
        selected = next(
            (
                item
                for item in pending
                if str(value(item, "approvalId", "id", default="")) == str(approval_id)
            ),
            None,
        )
        if selected is None:
            fail(runtime.console, "The requested pending approval was not found")
        return selected
    if len(pending) != 1:
        fail(
            runtime.console,
            "Specify --approval-id when the workflow does not have exactly one pending approval",
        )
    return pending[0]


def _decide(
    runtime: CliRuntime,
    workflow_id: uuid.UUID,
    source: Any,
    approval: dict[str, Any],
    decision: str,
    reason: str | None,
) -> Any:
    workflow_version = value(approval, "workflowVersion")
    if workflow_version is None and isinstance(source, dict):
        workflow_version = value(source, "workflowVersion", "version")
    if workflow_version is None:
        workflow = api_json(runtime, "GET", f"/api/v1/workflows/{workflow_id}")
        workflow_version = value(workflow, "workflowVersion", "version")
    required = {
        "approvalId": value(approval, "approvalId", "id"),
        "artifactId": value(approval, "artifactId"),
        "artifactVersion": value(approval, "artifactVersion"),
        "status": decision,
        "reason": reason,
        "workflowVersion": workflow_version,
    }
    if any(
        required[key] is None
        for key in ("approvalId", "artifactId", "artifactVersion", "workflowVersion")
    ):
        fail(runtime.console, "The approval response is missing exact-version decision fields")
    return api_json(
        runtime,
        "POST",
        f"/api/v1/workflows/{workflow_id}/approvals",
        json_body=required,
        reviewer=True,
    )
