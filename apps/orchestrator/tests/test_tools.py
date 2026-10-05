"""Real filesystem operations and adversarial workspace/command boundaries."""

import io
import os
import tarfile
import uuid

import pytest
from agents.tool_context import ToolContext

from app.agents.errors import AgentToolDenied
from app.agents.implementation import ImplementationAgent
from app.agents.requirement import RequirementAgent
from app.tools.commands import command_profile
from app.tools.engineering import engineering_tools
from app.tools.runner import DockerRunner
from app.tools.workspaces import MAX_FILE_BYTES, WorkspaceManager


@pytest.fixture
def workspace(tmp_path):
    with WorkspaceManager(tmp_path / "workspaces").for_workflow(uuid.uuid4()) as value:
        yield value


def test_files_write_read_search_patch_and_archive(workspace):
    receipt = workspace.write_file("src/app.py", "def value():\n    return 1\n")
    assert receipt["action"] == "created"
    assert workspace.list_files() == ["src/app.py"]
    assert workspace.search_code("return") == ["src/app.py:2:     return 1"]
    changed = workspace.apply_patch("src/app.py", "return 1", "return 2")
    assert changed["sha256"] != receipt["sha256"]
    assert workspace.read_file(str(workspace.path / "src/app.py")).endswith("return 2\n")
    data, sha = workspace.archive()
    assert len(sha) == 64
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        assert archive.getnames() == ["src/app.py"]
        assert archive.extractfile("src/app.py").read().endswith(b"return 2\n")


def test_generated_secret_is_rejected_before_workspace_write(workspace):
    fake_credential = "FAKE_TEST_TOKEN_123456789"
    with pytest.raises(AgentToolDenied, match="credential-like"):
        workspace.write_file("src/generated.py", f"token={fake_credential}")
    assert workspace.list_files() == []


@pytest.mark.parametrize(
    "path",
    [
        "../escape",
        "src/../../escape",
        "/etc/passwd",
        ".env",
        "a/.env.production",
        ".ssh/id_rsa",
        ".aws/credentials",
        ".docker/config.json",
        "credentials.json",
        "token.key",
        "certificate.pem",
        "var/run/docker.sock",
        ".netrc",
        "secrets.json",
        "a\\..\\outside",
        "C:/outside",
        "src/./file",
    ],
)
def test_forbidden_paths_for_every_file_operation(workspace, path):
    for operation in (
        lambda: workspace.read_file(path),
        lambda: workspace.write_file(path, "secret"),
        lambda: workspace.apply_patch(path, "a", "b"),
    ):
        with pytest.raises(AgentToolDenied):
            operation()


def test_cross_workflow_access_denied(tmp_path):
    manager = WorkspaceManager(tmp_path / "workspaces")
    with manager.for_workflow(uuid.uuid4()) as first, manager.for_workflow(uuid.uuid4()) as second:
        first.write_file("private.txt", "first workflow only")
        with pytest.raises(AgentToolDenied):
            second.read_file(str(first.path / "private.txt"))
        with pytest.raises(AgentToolDenied):
            second.write_file(f"../{first.workflow_id}/private.txt", "overwrite")
        assert first.read_file("private.txt") == "first workflow only"


@pytest.mark.parametrize("kind", ["file_symlink", "directory_symlink", "hardlink", "fifo"])
def test_links_and_special_files_are_not_capabilities(workspace, tmp_path, kind):
    outside = tmp_path / "outside"
    outside.mkdir()
    secret = outside / "secret.txt"
    secret.write_text("unchanged")
    path = workspace.path / "escape"
    if kind == "file_symlink":
        path.symlink_to(secret)
        target = "escape"
    elif kind == "directory_symlink":
        path.symlink_to(outside, target_is_directory=True)
        target = "escape/secret.txt"
    elif kind == "hardlink":
        os.link(secret, path)
        target = "escape"
    else:
        os.mkfifo(path)
        target = "escape"
    with pytest.raises(AgentToolDenied):
        workspace.read_file(target)
    with pytest.raises(AgentToolDenied):
        workspace.write_file(target, "overwrite")
    assert secret.read_text() == "unchanged"
    assert workspace.list_files() == []
    data, _ = workspace.archive()
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        assert archive.getnames() == []


def test_workflow_root_symlink_rejected(tmp_path):
    manager = WorkspaceManager(tmp_path / "workspaces")
    workflow_id = uuid.uuid4()
    (manager.root / str(workflow_id)).symlink_to(tmp_path)
    with pytest.raises(AgentToolDenied):
        manager.for_workflow(workflow_id)


def test_secrets_omitted_from_listing_search_and_runner_archive(workspace):
    (workspace.path / ".env").write_text("SECRET_VALUE")
    (workspace.path / "credentials.json").write_text("SECRET_VALUE")
    workspace.write_file("main.py", "public")
    assert workspace.list_files() == ["main.py"]
    assert workspace.search_code("SECRET") == []
    data, _ = workspace.archive()
    assert b"SECRET_VALUE" not in data


def test_patch_stale_and_ambiguous_fail_without_writes(workspace):
    workspace.write_file("file.txt", "same same")
    for old in ("", "missing", "same"):
        with pytest.raises(AgentToolDenied):
            workspace.apply_patch("file.txt", old, "new")
    assert workspace.read_file("file.txt") == "same same"


def test_file_search_and_workspace_budgets(workspace, monkeypatch):
    with pytest.raises(AgentToolDenied):
        workspace.write_file("big", "x" * (MAX_FILE_BYTES + 1))
    workspace.write_file("many", "match\n" * 200)
    assert len(workspace.search_code("match")) == 100
    with pytest.raises(AgentToolDenied):
        workspace.search_code("")
    monkeypatch.setattr("app.tools.workspaces.MAX_WORKSPACE_BYTES", 4)
    with pytest.raises(AgentToolDenied):
        workspace.write_file("other", "new")
    with pytest.raises(AgentToolDenied):
        workspace.archive()


@pytest.mark.parametrize(
    "command",
    [
        "sh",
        "bash -c pytest",
        "pytest; touch /tmp/owned",
        "pytest && env",
        "pytest -s",
        "mvn test -Dsomething=bad",
        "./mvnw test",
        "mvn package\nwhoami",
        "$(id)",
        "python -c print(1)",
        "docker ps",
        "pytest ",
        "mvn deploy",
    ],
)
@pytest.mark.asyncio
async def test_no_arbitrary_commands(workspace, command, monkeypatch):
    async def forbidden(*args):
        pytest.fail("Rejected command must not reach Docker")

    runner = DockerRunner()
    monkeypatch.setattr(runner, "_docker", forbidden)
    for build in (True, False):
        with pytest.raises(AgentToolDenied):
            await runner.run(workspace, command, build=build)


def test_command_operation_allowlist():
    assert command_profile("mvn test", build=False)[-1] == "test"
    assert command_profile("mvn package", build=True)[-1] == "package"
    assert command_profile("pytest", build=False)[-1] == "pytest"
    with pytest.raises(AgentToolDenied):
        command_profile("mvn package", build=False)


@pytest.mark.asyncio
@pytest.mark.parametrize("project", ["../other", "/tmp", ".env", "src/../other", ".ssh"])
async def test_command_project_cannot_escape(workspace, project, monkeypatch):
    runner = DockerRunner()

    async def forbidden(*args):
        pytest.fail("Invalid project must be rejected before Docker")

    monkeypatch.setattr(runner, "_docker", forbidden)
    with pytest.raises(AgentToolDenied):
        await runner.run(workspace, "pytest", build=False, project=project)


@pytest.mark.asyncio
async def test_sdk_tool_permissions_and_receipts(workspace, agent_context):
    context = agent_context.model_copy(
        update={
            "workflow_id": workspace.workflow_id,
            "authorized_tools": ("write_file", "read_file", "apply_patch"),
        }
    )
    receipts = []
    tools = {
        tool.name: tool
        for tool in engineering_tools(
            ImplementationAgent(), context, workspace, DockerRunner(), receipts
        )
    }
    ctx = ToolContext(
        context=context, tool_name="write_file", tool_call_id="test", tool_arguments="{}"
    )
    await tools["write_file"].on_invoke_tool(ctx, '{"path":"app.py","content":"return 1"}')
    assert workspace.read_file("app.py") == "return 1"
    assert receipts[0]["path"] == "app.py"
    assert receipts[0]["action"] == "created"
    wrong = ToolContext(
        context=agent_context, tool_name="write_file", tool_call_id="test", tool_arguments="{}"
    )
    with pytest.raises(AgentToolDenied):
        await tools["write_file"].on_invoke_tool(wrong, '{"path":"app.py","content":"bad"}')
    with pytest.raises(AgentToolDenied):
        engineering_tools(RequirementAgent(), context, workspace, DockerRunner(), [])
    with pytest.raises(AgentToolDenied):
        engineering_tools(ImplementationAgent(), agent_context, workspace, DockerRunner(), [])
