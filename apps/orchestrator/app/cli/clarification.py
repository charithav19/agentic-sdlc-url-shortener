"""Clarification CLI commands."""

import uuid
from typing import Annotated, Any

import typer

from app.cli.client import CliRuntime, api_json, fail, runtime_from
from app.cli.rendering import collection, emit, render_clarifications, render_result_panel, value

app = typer.Typer(help="Inspect and answer blocking clarification questions.", no_args_is_help=True)


@app.command("list")
def list_clarifications(context: typer.Context, workflow_id: uuid.UUID) -> None:
    runtime = runtime_from(context)
    result = _load(runtime, workflow_id)
    emit(
        runtime.console,
        result,
        lambda console, payload: render_result_panel(console, payload, "Clarification submitted"),
        json_output=runtime.json_output,
    )


@app.command("answer")
def answer_clarification(
    context: typer.Context,
    workflow_id: uuid.UUID,
    question_id: Annotated[str | None, typer.Option("--question-id")] = None,
    answer: Annotated[str | None, typer.Option("--answer")] = None,
    reason: Annotated[str | None, typer.Option("--reason")] = None,
) -> None:
    runtime = runtime_from(context)
    source = _load(runtime, workflow_id)
    selected = _select_question(runtime, source, question_id)
    answer_text = answer or typer.prompt(str(value(selected, "question", default="Answer")))
    if not answer_text.strip():
        fail(runtime.console, "A clarification answer is required")
    artifact_id = value(selected, "clarificationArtifactId") or value(
        source, "clarificationArtifactId"
    )
    artifact_version = value(selected, "clarificationArtifactVersion") or value(
        source, "clarificationArtifactVersion"
    )
    if artifact_id is None or artifact_version is None:
        fail(runtime.console, "Clarification response lacks its exact artifact version")
    body = {
        "clarificationArtifactId": artifact_id,
        "clarificationArtifactVersion": artifact_version,
        "answers": [
            {
                "question": value(selected, "question"),
                "answer": answer_text,
            }
        ],
        "expectedWorkflowVersion": value(source, "workflowVersion", "version"),
        "reason": reason,
    }
    result = api_json(
        runtime,
        "POST",
        f"/api/v1/workflows/{workflow_id}/clarifications",
        json_body={key: item for key, item in body.items() if item is not None},
        reviewer=True,
    )
    emit(runtime.console, result, render_clarifications, json_output=runtime.json_output)


def _load(runtime: CliRuntime, workflow_id: uuid.UUID) -> Any:
    return api_json(runtime, "GET", f"/api/v1/workflows/{workflow_id}/clarifications")


def _select_question(runtime: CliRuntime, payload: Any, question_id: str | None) -> dict[str, Any]:
    questions = collection(payload, "clarifications", "questions", "items")
    pending = [item for item in questions if value(item, "status", default="PENDING") == "PENDING"]
    if question_id is not None:
        selected = next(
            (
                item
                for item in pending
                if str(value(item, "questionId", "id", default="")) == question_id
            ),
            None,
        )
        if selected is None:
            fail(runtime.console, "The requested pending question was not found")
        return selected
    if len(pending) != 1:
        fail(runtime.console, "Specify --question-id unless exactly one question is pending")
    return pending[0]
