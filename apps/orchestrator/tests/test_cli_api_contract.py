"""CLI API payloads, approval safety, errors, and audit contracts."""

import uuid
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

import httpx
import pytest
from typer.testing import CliRunner

from app.cli import main as cli_main
from app.cli.client import ApiClient, ApiConnectionError, ApiError, CliConfigError

runner = CliRunner()
WORKFLOW_ID = uuid.UUID("10000000-0000-0000-0000-000000000001")
APPROVAL_ID = uuid.UUID("10000000-0000-0000-0000-000000000002")
ARTIFACT_ID = uuid.UUID("10000000-0000-0000-0000-000000000003")


class ContractClient:
    def __init__(self) -> None:
        self.responses: dict[tuple[str, str], deque[Any]] = defaultdict(deque)
        self.calls: list[dict[str, Any]] = []

    def add(self, method: str, path: str, *responses: Any) -> None:
        self.responses[(method, path)].extend(responses)

    def request_json(self, method, path, *, json_body=None, params=None, reviewer=False):
        self.calls.append(
            {
                "method": method,
                "path": path,
                "json": json_body,
                "params": params,
                "reviewer": reviewer,
            }
        )
        response = self.responses[(method, path)].popleft()
        if isinstance(response, Exception):
            raise response
        return response

    def request_text(self, method, path, *, params=None):
        self.calls.append({"method": method, "path": path, "params": params})
        response = self.responses[(method, path)].popleft()
        if isinstance(response, Exception):
            raise response
        return response

    def close(self) -> None:
        pass


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> ContractClient:
    result = ContractClient()
    monkeypatch.setattr(cli_main, "make_api_client", lambda _base_url: result)
    return result


def approval_list() -> dict[str, Any]:
    return {
        "workflowVersion": 7,
        "approvals": [
            {
                "approvalId": str(APPROVAL_ID),
                "approvalType": "ARCHITECTURE",
                "status": "PENDING",
                "artifactId": str(ARTIFACT_ID),
                "artifactVersion": 3,
                "artifactHash": "a" * 64,
                "risk": "Schema change",
            }
        ],
    }


def test_approval_never_submits_without_explicit_confirmation(client: ContractClient) -> None:
    path = f"/api/v1/workflows/{WORKFLOW_ID}/approvals"
    client.add("GET", path, approval_list())

    result = runner.invoke(cli_main.app, ["approval", "approve", str(WORKFLOW_ID)], input="n\n")

    assert result.exit_code == 1
    assert "Approve this exact artifact version?" in result.stdout
    assert [call["method"] for call in client.calls] == ["GET"]


def test_approval_posts_exact_artifact_and_workflow_versions(client: ContractClient) -> None:
    path = f"/api/v1/workflows/{WORKFLOW_ID}/approvals"
    client.add("GET", path, approval_list())
    client.add(
        "POST",
        path,
        {
            "approvalId": str(APPROVAL_ID),
            "status": "APPROVED",
            "artifactId": str(ARTIFACT_ID),
            "artifactVersion": 3,
            "workflowStatus": "RUNNING",
            "workflowVersion": 8,
        },
    )

    result = runner.invoke(
        cli_main.app,
        [
            "approval",
            "approve",
            str(WORKFLOW_ID),
            "--approval-id",
            str(APPROVAL_ID),
            "--yes",
        ],
    )

    assert result.exit_code == 0, result.output
    decision = client.calls[1]
    assert decision["reviewer"] is True
    assert decision["json"] == {
        "approvalId": str(APPROVAL_ID),
        "artifactId": str(ARTIFACT_ID),
        "artifactVersion": 3,
        "status": "APPROVED",
        "reason": None,
        "workflowVersion": 7,
    }


def test_rejection_requires_reason_and_posts_human_decision(client: ContractClient) -> None:
    path = f"/api/v1/workflows/{WORKFLOW_ID}/approvals"
    client.add("GET", path, approval_list())
    client.add("POST", path, {"approvalId": str(APPROVAL_ID), "status": "REJECTED"})

    result = runner.invoke(
        cli_main.app,
        ["approval", "reject", str(WORKFLOW_ID), "--reason", "Unsafe schema", "--yes"],
    )

    assert result.exit_code == 0
    assert client.calls[1]["json"]["reason"] == "Unsafe schema"
    assert client.calls[1]["reviewer"] is True


def test_clarification_answer_uses_exact_artifact_version(client: ContractClient) -> None:
    path = f"/api/v1/workflows/{WORKFLOW_ID}/clarifications"
    client.add(
        "GET",
        path,
        {
            "workflowVersion": 4,
            "clarificationArtifactId": str(ARTIFACT_ID),
            "clarificationArtifactVersion": 2,
            "questions": [
                {"questionId": "https", "question": "Require HTTPS?", "status": "PENDING"}
            ],
        },
    )
    client.add("POST", path, {"workflowStatus": "RUNNING", "requirementVersion": 2})

    result = runner.invoke(
        cli_main.app,
        [
            "clarification",
            "answer",
            str(WORKFLOW_ID),
            "--question-id",
            "https",
            "--answer",
            "Yes",
        ],
    )

    assert result.exit_code == 0, result.output
    assert client.calls[1]["reviewer"] is True
    assert client.calls[1]["json"] == {
        "clarificationArtifactId": str(ARTIFACT_ID),
        "clarificationArtifactVersion": 2,
        "answers": [{"question": "Require HTTPS?", "answer": "Yes"}],
        "expectedWorkflowVersion": 4,
    }


def test_requirement_update_reads_file_and_does_not_write_database(
    client: ContractClient, tmp_path: Path
) -> None:
    requirement_file = tmp_path / "update.md"
    requirement_file.write_text("Expired links return 410 Gone.", encoding="utf-8")
    path = f"/api/v1/workflows/{WORKFLOW_ID}/requirements"
    client.add("POST", path, {"workflowStatus": "REPLANNING", "requirementVersion": 2})

    result = runner.invoke(
        cli_main.app,
        [
            "requirement",
            "update",
            str(WORKFLOW_ID),
            "--file",
            str(requirement_file),
            "--workflow-version",
            "5",
        ],
    )

    assert result.exit_code == 0
    body = client.calls[0]["json"]
    assert body["requirement"] == "Expired links return 410 Gone."
    assert body["expectedWorkflowVersion"] == 5
    assert uuid.UUID(body["updateId"])
    assert client.calls[0]["reviewer"] is True


def test_audit_passes_bounded_pagination_and_renders_timeline(client: ContractClient) -> None:
    path = f"/api/v1/workflows/{WORKFLOW_ID}/audit"
    client.add(
        "GET",
        path,
        {
            "events": [
                {
                    "sequence": 9,
                    "occurredAt": "2026-10-04T12:00:00Z",
                    "eventType": "WORKFLOW_STATUS_CHANGED",
                    "actorId": "orchestrator",
                    "beforeState": "CREATED",
                    "afterState": "RUNNING",
                }
            ]
        },
    )

    result = runner.invoke(
        cli_main.app,
        ["audit", str(WORKFLOW_ID), "--after-sequence", "8", "--limit", "25"],
    )

    assert result.exit_code == 0
    assert client.calls[0]["params"] == {"afterSequence": 8, "limit": 25}
    assert "orchestrator" in result.stdout
    assert "CREATED" in result.stdout and "RUNNING" in result.stdout


@pytest.mark.parametrize(
    ("error", "exit_code", "expected"),
    [
        (
            ApiError(409, "Artifact version is stale", code="CONFLICT", trace_id="trace-1"),
            4,
            "trace-1",
        ),
        (ApiError(503, "Database unavailable"), 5, "Database unavailable"),
        (ApiConnectionError("Cannot reach orchestrator"), 3, "Cannot reach orchestrator"),
    ],
)
def test_structured_errors_have_stable_exit_codes_without_secrets(
    client: ContractClient, error: Exception, exit_code: int, expected: str
) -> None:
    client.add("GET", f"/api/v1/workflows/{WORKFLOW_ID}", error)

    result = runner.invoke(cli_main.app, ["workflow", "status", str(WORKFLOW_ID)])

    assert result.exit_code == exit_code
    assert expected in result.stdout
    assert "ORCHESTRATOR_LOCAL_REVIEWER_TOKEN" not in result.stdout
    assert "Bearer" not in result.stdout


def test_real_http_client_sends_json_and_reviewer_headers() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("Authorization")
        captured["reviewer"] = request.headers.get("X-Reviewer-Id")
        captured["body"] = request.read().decode()
        return httpx.Response(200, json={"status": "APPROVED"})

    client = ApiClient(
        "http://orchestrator.test",
        reviewer_token="fake-review-token",
        reviewer_id="test-reviewer",
        transport=httpx.MockTransport(handler),
    )
    try:
        result = client.request_json(
            "POST",
            "/api/v1/workflows/one/approvals",
            json_body={"status": "APPROVED"},
            reviewer=True,
        )
    finally:
        client.close()

    assert result == {"status": "APPROVED"}
    assert captured == {
        "method": "POST",
        "url": "http://orchestrator.test/api/v1/workflows/one/approvals",
        "authorization": "Bearer fake-review-token",
        "reviewer": "test-reviewer",
        "body": '{"status":"APPROVED"}',
    }


def test_http_client_maps_fastapi_error_without_echoing_response_internals() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            409,
            headers={"X-Trace-Id": "trace-header"},
            json={
                "error": {"code": "HTTP_ERROR", "message": "Stale workflow version"},
                "traceId": "trace-body",
            },
        )

    client = ApiClient("http://orchestrator.test", transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(ApiError) as captured:
            client.request_json("GET", "/api/v1/workflows/one")
    finally:
        client.close()

    assert captured.value.status_code == 409
    assert captured.value.code == "HTTP_ERROR"
    assert captured.value.message == "Stale workflow version"
    assert captured.value.trace_id == "trace-body"


def test_http_client_requires_header_credential_for_human_writes() -> None:
    client = ApiClient(
        "http://orchestrator.test",
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={})),
    )
    try:
        with pytest.raises(CliConfigError, match="LOCAL_REVIEWER_TOKEN"):
            client.request_json("POST", "/api/v1/workflows/one/approvals", reviewer=True)
    finally:
        client.close()
