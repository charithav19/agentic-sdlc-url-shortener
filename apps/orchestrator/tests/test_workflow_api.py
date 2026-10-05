"""HTTP workflow adapters exercise durable domain state and real scheduler checkpoints."""

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.api.dependencies import get_orchestrator
from app.api.workflows import get_workflow_runtime
from app.governance.auth import ReviewerIdentity, require_reviewer
from app.main import app
from app.orchestration.contracts import ScenarioType
from app.orchestration.workflow_runtime import WorkflowRuntime
from app.orchestration.workflows import CreateWorkflow, WorkflowService
from app.persistence.models import Artifact, AuditEvent, StageRun, WorkflowRun
from app.persistence.session import session_scope
from app.scenarios.fixtures import ScenarioFixtureLoader
from app.tools.workspaces import WorkspaceManager


@pytest_asyncio.fixture
async def workflow_api(phase6_factory, tmp_path):
    service = WorkflowService(
        phase6_factory,
        workspaces=WorkspaceManager(tmp_path / "workspaces"),
        loader=ScenarioFixtureLoader(),
    )
    runtime = WorkflowRuntime(service)
    previous = getattr(app.state, "workflow_runtime", None)
    app.state.workflow_runtime = runtime
    app.dependency_overrides[get_workflow_runtime] = lambda: runtime
    app.dependency_overrides[get_orchestrator] = lambda: runtime.orchestrator
    app.dependency_overrides[require_reviewer] = lambda: ReviewerIdentity("workflow-api-test")
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client, runtime
    finally:
        await runtime.close()
        app.dependency_overrides.clear()
        if previous is not None:
            app.state.workflow_runtime = previous
        else:
            del app.state.workflow_runtime


async def start(client, runtime, scenario="GREENFIELD", **body):
    response = await client.post(
        "/api/v1/workflows", json={"scenario": scenario, "demo": True, **body}
    )
    assert response.status_code == 201, response.text
    document = response.json()
    identifier = uuid.UUID(document["workflowId"])
    # Calling schedule twice must still use the durable claim and execute each stage once.
    runtime.schedule(identifier)
    await runtime.wait(identifier)
    return identifier, document


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_persists_requirement_graph_stages_and_audit(workflow_api):
    client, runtime = workflow_api
    identifier, document = await start(
        client, runtime, requirement="Build a URL shortener with HTTP redirects."
    )
    assert document["status"] == "CREATED"
    assert document["workflowVersion"] == 1
    assert document["providerMode"] == "fake"
    assert len(document["stages"]) == 16
    async with session_scope(runtime.factory) as session:
        workflow = await session.get(WorkflowRun, identifier)
        assert workflow.workspace_ref == f"workspaces/{identifier}"
        requirement = await session.scalar(
            select(Artifact).where(
                Artifact.workflow_id == identifier, Artifact.logical_name == "requirement"
            )
        )
        assert requirement.content["requirement"] == "Build a URL shortener with HTTP redirects."
        assert workflow.graph_revision_id is not None
        stages = list(
            await session.scalars(select(StageRun).where(StageRun.workflow_id == identifier))
        )
        assert len(stages) == 16
        assert all(s.attempt == 1 for s in stages)
        analysis = next(s for s in stages if s.stage_name == "REQUIREMENT_ANALYSIS")
        assert analysis.lease_token is None
        events = list(
            await session.scalars(
                select(AuditEvent.event_type).where(AuditEvent.workflow_id == identifier)
            )
        )
        assert "WORKFLOW_CREATED" in events
        assert "APPROVAL_REQUESTED" in events
    assert (runtime.service.workspaces.root / str(identifier)).is_dir()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_status_and_graph_are_persisted_read_only_projections(workflow_api):
    client, runtime = workflow_api
    identifier, _ = await start(client, runtime)
    response = await client.get(f"/api/v1/workflows/{identifier}")
    assert response.status_code == 200
    status = response.json()
    assert status["status"] == "WAITING_FOR_APPROVAL"
    assert status["workflowVersion"] >= 2
    assert status["blockers"]
    action = status["pendingHumanAction"][0]
    assert action["approvalType"] == "ARCHITECTURE"
    assert action["artifactVersion"] == 1
    assert any(a["artifactId"] == action["artifactId"] for a in status["artifacts"])
    assert "exact pending artifact version" in status["nextAction"]
    graph = (await client.get(f"/api/v1/workflows/{identifier}/graph")).json()
    assert graph["graphHash"] == status["graphHash"]
    assert graph["workflowVersion"] == status["workflowVersion"]
    assert graph["graphRevisionId"]
    stages = {s["name"]: s for s in graph["stages"]}
    assert stages["BUILD_VALIDATION"]["dependencies"] == ["IMPLEMENTATION", "TEST_DESIGN"]
    assert stages["ARCHITECTURE_DESIGN"]["status"] == "SUCCEEDED"
    assert "ARCHITECTURE_APPROVAL" in graph["readyStages"]
    assert "IMPLEMENTATION" in graph["blockedStages"]
    assert stages["IMPLEMENTATION"]["startedAt"] is None
    again = (await client.get(f"/api/v1/workflows/{identifier}")).json()
    assert again["stateVersion"] == status["stateVersion"]


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("suffix", ["", "/graph"])
async def test_invalid_and_missing_workflow(workflow_api, suffix):
    client, _ = workflow_api
    invalid = await client.get(f"/api/v1/workflows/not-a-uuid{suffix}")
    assert invalid.status_code == 422
    missing = await client.get(f"/api/v1/workflows/{uuid.uuid4()}{suffix}")
    assert missing.status_code == 404
    assert missing.json()["traceId"] == missing.headers["X-Trace-Id"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ambiguous_workflow_pauses_before_downstream_work(workflow_api):
    client, runtime = workflow_api
    identifier, _ = await start(client, runtime, "AMBIGUOUS")
    status = (await client.get(f"/api/v1/workflows/{identifier}")).json()
    assert status["status"] == "WAITING_FOR_CLARIFICATION"
    action = status["pendingHumanAction"][0]
    assert action["kind"] == "CLARIFICATION"
    assert len(action["questions"]) == 6
    stages = {s["stageName"]: s for s in status["stages"]}
    for name in ("TASK_DECOMPOSITION", "ARCHITECTURE_DESIGN", "IMPLEMENTATION"):
        assert stages[name]["startedAt"] is None
        assert stages[name]["status"] != "SUCCEEDED"
    graph = (await client.get(f"/api/v1/workflows/{identifier}/graph")).json()
    assert len(graph["stages"]) == 17
    nodes = {s["name"]: s for s in graph["stages"]}
    assert nodes["TASK_DECOMPOSITION"]["dependencies"] == ["CLARIFICATION"]
    assert nodes["CLARIFICATION"]["status"] == "WAITING_APPROVAL"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_brownfield_inspects_source_and_reaches_real_approval(workflow_api):
    client, runtime = workflow_api
    identifier, _ = await start(client, runtime, "BROWNFIELD")
    status = (await client.get(f"/api/v1/workflows/{identifier}")).json()
    assert status["status"] == "WAITING_FOR_APPROVAL"
    async with session_scope(runtime.factory) as session:
        artifact = await session.scalar(
            select(Artifact).where(
                Artifact.workflow_id == identifier, Artifact.logical_name == "source-impact"
            )
        )
        assert any(p.endswith(".java") for p in artifact.content["inspectedFiles"])
        assert artifact.content["affectedFiles"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_approval_wrong_version_and_rejection_preserve_checkpoint(workflow_api):
    client, runtime = workflow_api
    identifier, _ = await start(client, runtime)
    status = (await client.get(f"/api/v1/workflows/{identifier}")).json()
    action = status["pendingHumanAction"][0]
    payload = {
        "approvalId": action["approvalId"],
        "artifactId": action["artifactId"],
        "artifactVersion": action["artifactVersion"] + 1,
        "status": "APPROVED",
        "workflowVersion": status["workflowVersion"],
    }
    assert (
        await client.post(f"/api/v1/workflows/{identifier}/approvals", json=payload)
    ).status_code == 409
    payload.update(
        artifactVersion=action["artifactVersion"], status="REJECTED", reason="Revise design"
    )
    assert (
        await client.post(f"/api/v1/workflows/{identifier}/approvals", json=payload)
    ).status_code == 200
    await runtime.wait(identifier)
    status = (await client.get(f"/api/v1/workflows/{identifier}")).json()
    assert status["status"] == "WAITING_FOR_APPROVAL"
    assert (
        next(s for s in status["stages"] if s["stageName"] == "IMPLEMENTATION")["startedAt"] is None
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_rejected_seed_and_missing_openai_configuration_do_not_create_workflows(
    workflow_api,
    monkeypatch,
):
    client, runtime = workflow_api
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("OPENAI_MODEL", "")
    async with session_scope(runtime.factory) as session:
        before = await session.scalar(select(func.count()).select_from(WorkflowRun))
    for body in ({"seedRef": "../../etc"}, {"providerMode": "openai"}):
        response = await client.post(
            "/api/v1/workflows",
            json={
                "scenario": "GREENFIELD",
                "demo": True,
                **body,
            },
        )
        assert response.status_code == 422
    async with session_scope(runtime.factory) as session:
        after = await session.scalar(select(func.count()).select_from(WorkflowRun))
    assert before == after
    assert not list(runtime.service.workspaces.root.iterdir())


@pytest.mark.parametrize(
    "body",
    [
        {"scenario": "NO_SUCH_SCENARIO", "demo": True},
        {"scenario": "GREENFIELD", "requirement": " "},
        {"scenario": "GREENFIELD", "requirement": "A", "providerMode": "invalid"},
        {"scenario": "GREENFIELD"},
    ],
)
def test_create_command_rejects_invalid_inputs(body):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        CreateWorkflow.model_validate(body)


def test_demo_can_use_packaged_requirement():
    command = CreateWorkflow(scenario=ScenarioType.GREENFIELD, demo=True)
    assert command.requirement is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_clarification_submission_wakes_analysis_and_preserves_versions(workflow_api):
    client, runtime = workflow_api
    identifier, _ = await start(client, runtime, "AMBIGUOUS")
    status = (await client.get(f"/api/v1/workflows/{identifier}")).json()
    action = status["pendingHumanAction"][0]
    response = await client.post(
        f"/api/v1/workflows/{identifier}/clarifications",
        json={
            "clarificationArtifactId": action["artifactId"],
            "clarificationArtifactVersion": action["artifactVersion"],
            "expectedWorkflowVersion": status["workflowVersion"],
            "answers": [
                {"question": q, "answer": "Require public HTTPS URLs; other changes excluded."}
                for q in action["questions"]
            ],
        },
    )
    assert response.status_code == 201, response.text
    await runtime.wait(identifier)
    status = (await client.get(f"/api/v1/workflows/{identifier}")).json()
    assert status["status"] == "WAITING_FOR_APPROVAL"
    assert status["generation"] == 2
    assert status["requirementVersion"] == 2
    assert status["pendingHumanAction"][0]["approvalType"] == "ARCHITECTURE"
    assert (
        next(s for s in status["stages"] if s["stageName"] == "IMPLEMENTATION")["startedAt"] is None
    )
    async with session_scope(runtime.factory) as session:
        versions = list(
            await session.scalars(
                select(Artifact.version)
                .where(Artifact.workflow_id == identifier, Artifact.logical_name == "requirement")
                .order_by(Artifact.version)
            )
        )
    assert versions == [1, 2]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_approval_wakes_parallel_work_but_missing_validation_never_fakes_success(
    workflow_api,
    monkeypatch,
):
    from app.agents.errors import AgentToolDenied
    from app.tools.runner import DockerRunner

    async def unavailable(*_args, **_kwargs):
        raise AgentToolDenied("Isolated runner unavailable for test")

    monkeypatch.setattr(DockerRunner, "run", unavailable)
    client, runtime = workflow_api
    identifier, _ = await start(client, runtime)
    status = (await client.get(f"/api/v1/workflows/{identifier}")).json()
    action = status["pendingHumanAction"][0]
    response = await client.post(
        f"/api/v1/workflows/{identifier}/approvals",
        json={
            "approvalId": action["approvalId"],
            "artifactId": action["artifactId"],
            "artifactVersion": action["artifactVersion"],
            "status": "APPROVED",
            "workflowVersion": status["workflowVersion"],
        },
    )
    assert response.status_code == 200, response.text
    await runtime.wait(identifier)
    status = (await client.get(f"/api/v1/workflows/{identifier}")).json()
    stages = {s["stageName"]: s for s in status["stages"]}
    assert status["status"] == "SAFE_STOPPED"
    for name in ("IMPLEMENTATION", "TEST_DESIGN", "DOCUMENTATION_DRAFT"):
        assert stages[name]["status"] == "SUCCEEDED", (
            stages[name]["errorMessage"],
            status["stopReason"],
        )
    assert stages["BUILD_VALIDATION"]["status"] == "SAFE_STOPPED"
    assert stages["COMPLETED"]["startedAt"] is None
    assert status["stopReason"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_graph_reads_pinned_revision_not_changed_configuration(workflow_api, monkeypatch):
    client, runtime = workflow_api
    identifier, _ = await start(client, runtime)

    def changed_config(*_args, **_kwargs):
        raise AssertionError("Read views must use the persisted graph revision")

    monkeypatch.setattr("app.orchestration.workflows.load_graph", changed_config)
    assert (await client.get(f"/api/v1/workflows/{identifier}/graph")).status_code == 200
    async with session_scope(runtime.factory) as session:
        workflow = await session.get(WorkflowRun, identifier)
        workflow.graph_hash = "0" * 64
    response = await client.get(f"/api/v1/workflows/{identifier}/graph")
    assert response.status_code == 409
    assert "Persisted workflow graph is invalid" in response.json()["error"]["message"]


def test_cli_json_remains_valid_at_narrow_terminal_width():
    import io
    import json

    from rich.console import Console

    from app.cli.rendering import emit

    output = io.StringIO()
    payload = {"nextAction": "Review this exact artifact version " * 8, "graphHash": "a" * 64}
    emit(Console(file=output, width=30), payload, None, json_output=True)
    assert json.loads(output.getvalue()) == payload
