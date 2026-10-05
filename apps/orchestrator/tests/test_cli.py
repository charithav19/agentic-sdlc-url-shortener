"""Typer command surface and Rich presentation behavior."""

import json
import uuid
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from app.cli import main as cli_main

runner = CliRunner()
WORKFLOW_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
ARTIFACT_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


class FakeClient:
    def __init__(self) -> None:
        self.json_responses: dict[tuple[str, str], deque[Any]] = defaultdict(deque)
        self.text_responses: dict[tuple[str, str], str] = {}
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    def add_json(self, method: str, path: str, *responses: Any) -> None:
        self.json_responses[(method, path)].extend(responses)

    def request_json(
        self,
        method: str,
        path: str,
        *,
        json_body=None,
        params=None,
        reviewer=False,
    ) -> Any:
        self.calls.append(
            {
                "method": method,
                "path": path,
                "json": json_body,
                "params": params,
                "reviewer": reviewer,
            }
        )
        responses = self.json_responses[(method, path)]
        if not responses:
            raise AssertionError(f"Unexpected API call: {method} {path}")
        response = responses[0] if len(responses) == 1 else responses.popleft()
        if isinstance(response, BaseException):
            raise response
        return response

    def request_text(self, method: str, path: str, *, params=None) -> str:
        self.calls.append({"method": method, "path": path, "params": params})
        return self.text_responses[(method, path)]

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def fake_client(monkeypatch: pytest.MonkeyPatch) -> FakeClient:
    client = FakeClient()
    monkeypatch.setattr(cli_main, "make_api_client", lambda _base_url: client)
    return client


def workflow_document(status: str = "RUNNING", version: int = 1) -> dict[str, Any]:
    return {
        "workflowId": str(WORKFLOW_ID),
        "status": status,
        "scenarioType": "GREENFIELD",
        "providerMode": "fake",
        "generation": 1,
        "workflowVersion": version,
        "stages": [
            {"stageName": "INTAKE", "status": "SUCCEEDED", "attempt": 1},
            {
                "stageName": "ARCHITECTURE_APPROVAL",
                "status": "BLOCKED",
                "attempt": 1,
                "blockedReason": "Waiting for architecture",
            },
        ],
        "nextAction": "Wait for architecture approval",
    }


def test_help_lists_every_requested_command() -> None:
    result = runner.invoke(cli_main.app, ["--help"])

    assert result.exit_code == 0
    for command in (
        "workflow",
        "approval",
        "artifact",
        "lineage",
        "clarification",
        "requirement",
        "audit",
        "metrics",
        "demo",
    ):
        assert command in result.stdout


@pytest.mark.parametrize(
    "command",
    [
        ("workflow", "create"),
        ("workflow", "status"),
        ("workflow", "watch"),
        ("workflow", "graph"),
        ("approval", "list"),
        ("approval", "approve"),
        ("approval", "reject"),
        ("artifact", "list"),
        ("artifact", "show"),
        ("lineage",),
        ("clarification", "list"),
        ("clarification", "answer"),
        ("requirement", "update"),
        ("audit",),
        ("metrics",),
        ("demo", "greenfield"),
        ("demo", "brownfield"),
        ("demo", "ambiguous"),
    ],
)
def test_every_requested_command_has_help(command: tuple[str, ...]) -> None:
    result = runner.invoke(cli_main.app, [*command, "--help"])

    assert result.exit_code == 0, result.output
    assert "Usage:" in result.stdout


def test_workflow_create_reads_requirement_and_renders_panel(
    fake_client: FakeClient, tmp_path: Path
) -> None:
    requirement_file = tmp_path / "requirement.md"
    requirement_file.write_text("Create a safe URL shortener.", encoding="utf-8")
    fake_client.add_json("POST", "/api/v1/workflows", workflow_document())

    result = runner.invoke(
        cli_main.app,
        [
            "workflow",
            "create",
            "--scenario",
            "greenfield",
            "--requirement-file",
            str(requirement_file),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Workflow" in result.stdout
    assert "GREENFIELD" in result.stdout
    assert fake_client.calls[0]["json"] == {
        "scenario": "GREENFIELD",
        "requirement": "Create a safe URL shortener.",
        "providerMode": "fake",
    }
    assert fake_client.closed


def test_status_json_mode_preserves_api_document(fake_client: FakeClient) -> None:
    document = workflow_document()
    fake_client.add_json("GET", f"/api/v1/workflows/{WORKFLOW_ID}", document)

    result = runner.invoke(
        cli_main.app,
        ["--json", "workflow", "status", str(WORKFLOW_ID)],
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout) == document


def test_status_remains_readable_without_color_in_a_narrow_terminal(
    fake_client: FakeClient,
) -> None:
    fake_client.add_json(
        "GET", f"/api/v1/workflows/{WORKFLOW_ID}", workflow_document("SAFE_STOPPED")
    )

    result = runner.invoke(
        cli_main.app,
        ["--no-color", "workflow", "status", str(WORKFLOW_ID)],
        env={"COLUMNS": "48"},
    )

    assert result.exit_code == 0
    assert "SAFE_STOPPED" in result.stdout
    assert "Wait for architecture approval" in result.stdout
    assert "\x1b[" not in result.stdout


def test_graph_and_lineage_use_rich_trees(fake_client: FakeClient) -> None:
    fake_client.add_json(
        "GET",
        f"/api/v1/workflows/{WORKFLOW_ID}/graph",
        {
            "graphHash": "abc123",
            "stages": [
                {"name": "A", "status": "SUCCEEDED", "dependencies": []},
                {"name": "B", "status": "READY", "dependencies": ["A"]},
            ],
        },
    )
    fake_client.add_json(
        "GET",
        f"/api/v1/workflows/{WORKFLOW_ID}/lineage",
        {
            "nodes": [
                {"artifactId": "a", "logicalName": "Requirement", "version": 1},
                {"artifactId": "b", "logicalName": "Architecture", "version": 1},
            ],
            "edges": [
                {"parentArtifactId": "a", "childArtifactId": "b", "relationship": "DERIVED_FROM"}
            ],
        },
    )

    graph = runner.invoke(cli_main.app, ["workflow", "graph", str(WORKFLOW_ID)])
    lineage = runner.invoke(cli_main.app, ["lineage", str(WORKFLOW_ID)])

    assert graph.exit_code == 0
    assert "Workflow graph" in graph.stdout and "depends on: A" in graph.stdout
    assert lineage.exit_code == 0
    assert "Artifact lineage" in lineage.stdout and "DERIVED_FROM" in lineage.stdout


def test_watch_stops_at_attention_state_without_cancelling(
    fake_client: FakeClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = f"/api/v1/workflows/{WORKFLOW_ID}"
    fake_client.add_json(
        "GET",
        path,
        workflow_document("RUNNING", 1),
        workflow_document("WAITING_FOR_APPROVAL", 2),
    )
    monkeypatch.setattr("app.cli.workflow.time.sleep", lambda _seconds: None)

    result = runner.invoke(
        cli_main.app,
        ["workflow", "watch", str(WORKFLOW_ID), "--interval", "0.1", "--max-polls", "3"],
    )

    assert result.exit_code == 0
    assert [call["method"] for call in fake_client.calls] == ["GET", "GET"]
    assert "WAITING_FOR_APPROVAL" in result.stdout


def test_watch_interrupt_exits_without_cancelling(fake_client: FakeClient) -> None:
    fake_client.add_json(
        "GET",
        f"/api/v1/workflows/{WORKFLOW_ID}",
        KeyboardInterrupt(),
    )

    result = runner.invoke(cli_main.app, ["workflow", "watch", str(WORKFLOW_ID)])

    assert result.exit_code == 130
    assert "workflow remains running" in result.stdout
    assert [call["method"] for call in fake_client.calls] == ["GET"]


def test_artifact_list_show_and_metrics_render_tables(fake_client: FakeClient) -> None:
    artifacts = {
        "artifacts": [
            {
                "artifactId": str(ARTIFACT_ID),
                "logicalName": "architecture",
                "artifactType": "architecture",
                "version": 2,
                "status": "ACTIVE",
            }
        ]
    }
    fake_client.add_json("GET", f"/api/v1/workflows/{WORKFLOW_ID}/artifacts", artifacts)
    fake_client.add_json(
        "GET",
        f"/api/v1/workflows/{WORKFLOW_ID}/artifacts/{ARTIFACT_ID}",
        {
            **artifacts["artifacts"][0],
            "sha256": "a" * 64,
            "content": {"components": ["api", "database"]},
        },
    )
    fake_client.text_responses[("GET", "/metrics")] = (
        "# TYPE workflow_completed_total counter\n"
        "workflow_completed_total 3\n"
        "# TYPE workflow_success_rate gauge\n"
        "workflow_success_rate 0.75\n"
    )

    listed = runner.invoke(cli_main.app, ["artifact", "list", str(WORKFLOW_ID)])
    shown = runner.invoke(
        cli_main.app,
        ["artifact", "show", str(WORKFLOW_ID), str(ARTIFACT_ID)],
    )
    metrics = runner.invoke(cli_main.app, ["metrics"])

    assert listed.exit_code == 0 and "architecture" in listed.stdout
    assert shown.exit_code == 0 and "components" in shown.stdout
    assert metrics.exit_code == 0 and "workflow_success_rate" in metrics.stdout


@pytest.mark.parametrize("scenario", ["greenfield", "brownfield", "ambiguous"])
def test_demo_commands_delegate_to_fastapi(fake_client: FakeClient, scenario: str) -> None:
    fake_client.add_json("POST", "/api/v1/workflows", workflow_document())

    result = runner.invoke(cli_main.app, ["demo", scenario])

    assert result.exit_code == 0
    assert fake_client.calls[0]["path"] == "/api/v1/workflows"
    assert fake_client.calls[0]["json"] == {
        "scenario": scenario.upper(),
        "demo": True,
        "providerMode": "fake",
    }
