"""Real disposable containers: command success/failure, isolation and cleanup."""

import asyncio
import os
import uuid
from pathlib import Path

import pytest

from app.agents.errors import AgentToolDenied
from app.tools.runner import DockerRunner
from app.tools.workspaces import WorkspaceManager

pytestmark = [pytest.mark.runner, pytest.mark.asyncio]


@pytest.fixture
def candidate(tmp_path):
    if os.environ.get("RUN_RUNNER_TESTS") != "1":
        pytest.skip("Use make test-runner to execute isolated Docker tests")
    with WorkspaceManager(tmp_path / "workspaces").for_workflow(uuid.uuid4()) as workspace:
        yield workspace


async def test_pytest_isolation_and_no_host_effects(candidate, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "host-only-canary")
    candidate.write_file(
        "test_isolation.py",
        """
import os, socket
from pathlib import Path

def test_isolation():
    assert os.getuid() == 10001
    assert "OPENAI_API_KEY" not in os.environ
    assert not Path("/var/run/docker.sock").exists()
    assert not Path("/Users").exists()
    assert "CapEff:\\t0000000000000000" in Path("/proc/self/status").read_text()
    assert "NoNewPrivs:\\t1" in Path("/proc/self/status").read_text()
    assert Path("/sys/fs/cgroup/pids.max").read_text().strip() == "128"
    assert Path("/sys/fs/cgroup/memory.max").read_text().strip() == str(768 * 1024 * 1024)
    assert Path("/sys/fs/cgroup/cpu.max").read_text().startswith("100000 ")
    with socket.socket() as client:
        client.settimeout(0.2)
        assert client.connect_ex(("1.1.1.1", 443)) != 0
    try:
        Path("/opt/host-write").write_text("forbidden")
    except OSError:
        pass
    else:
        raise AssertionError("Root filesystem writable")
    Path("/workspace/container-only").write_text("ephemeral")
""",
    )
    result = await DockerRunner().run(candidate, "pytest", build=False)
    assert result.exit_code == 0, result.output
    assert result.error is None
    assert "1 passed" in result.output
    assert not (candidate.path / "container-only").exists()
    assert "host-only-canary" not in result.output


async def test_java_test_and_package(candidate):
    infra = Path(__file__).resolve().parents[3] / "infra/runner"
    candidate.write_file("pom.xml", (infra / "pom.xml").read_text())
    candidate.write_file("src/test/java/WarmupTest.java", (infra / "WarmupTest.java").read_text())
    for command, build in (("mvn test", False), ("mvn package", True)):
        result = await DockerRunner().run(candidate, command, build=build)
        assert result.exit_code == 0, result.output
        assert "BUILD SUCCESS" in result.output
        assert result.candidate_sha256
        assert result.image_id.startswith("sha256:")
    assert not (candidate.path / "target").exists()


async def test_actual_failure_is_not_success(candidate):
    candidate.write_file("test_bad.py", "def test_bad():\n    assert False\n")
    result = await DockerRunner().run(candidate, "pytest", build=False)
    assert result.exit_code == 1
    assert result.error == "COMMAND_FAILED"
    assert "1 failed" in result.output


async def test_timeout_destroys_container(candidate):
    candidate.write_file("test_slow.py", "import time\ndef test_slow():\n    time.sleep(60)\n")
    runner = DockerRunner(timeout_seconds=1)
    result = await runner.run(candidate, "pytest", build=False)
    assert result.error == "TIMEOUT"
    assert result.exit_code is None
    assert await runner._docker("ps", "-aq", "--filter", "name=schwab-run-") == ""


async def test_output_limit_destroys_container(candidate):
    candidate.write_file("conftest.py", "import os\nos.write(1, b'x' * 100000)\n")
    runner = DockerRunner()
    result = await runner.run(candidate, "pytest", build=False)
    assert result.error == "OUTPUT_LIMIT"
    assert len(result.output.encode()) <= 64000
    assert await runner._docker("ps", "-aq", "--filter", "name=schwab-run-") == ""


async def test_cancellation_destroys_container(candidate):
    candidate.write_file("test_slow.py", "import time\ndef test_slow():\n    time.sleep(60)\n")
    runner = DockerRunner()
    started = asyncio.Event()
    original = runner.verify_container

    def verify(info):
        original(info)
        started.set()

    runner.verify_container = verify
    task = asyncio.create_task(runner.run(candidate, "pytest", build=False))
    await asyncio.wait_for(started.wait(), timeout=15)
    await asyncio.sleep(0.2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert await runner._docker("ps", "-aq", "--filter", "name=schwab-run-") == ""


async def test_inspection_failure_prevents_execution(candidate, monkeypatch):
    candidate.write_file("test_ok.py", "def test_ok():\n    assert True\n")
    runner = DockerRunner()

    def reject(info):
        raise AgentToolDenied("Injected isolation rejection")

    monkeypatch.setattr(runner, "verify_container", reject)
    with pytest.raises(AgentToolDenied, match="Injected isolation"):
        await runner.run(candidate, "pytest", build=False)
    assert await runner._docker("ps", "-aq", "--filter", "name=schwab-run-") == ""
