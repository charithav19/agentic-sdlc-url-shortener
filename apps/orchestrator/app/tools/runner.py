"""Trusted Docker control plane. No mounts or secrets cross into candidate execution."""

import asyncio
import json
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from app.agents.errors import AgentToolDenied
from app.tools.commands import command_profile
from app.tools.workspaces import Workspace, validate_parts

OUTPUT_LIMIT = 64_000


class OutputLimit(Exception):
    pass


@dataclass(frozen=True)
class CommandResult:
    invocation_id: str
    workflow_id: str
    command: tuple[str, ...]
    project: str
    candidate_sha256: str
    image_id: str
    started_at: str
    finished_at: str
    exit_code: int | None
    output: str
    error: str | None

    def as_dict(self):
        return asdict(self)


class DockerRunner:
    def __init__(self, image: str = "schwab-engineering-runner:local", timeout_seconds: float = 30):
        if not 0 < timeout_seconds <= 120:
            raise ValueError("Runner deadline must be between 0 and 120 seconds")
        self.image = image
        self.timeout_seconds = timeout_seconds

    async def _docker(self, *args: str) -> str:
        process = await asyncio.create_subprocess_exec(
            "docker",
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=15)
        except BaseException:
            if process.returncode is None:
                process.kill()
            await process.wait()
            raise
        if process.returncode:
            raise AgentToolDenied("Docker runner unavailable or policy verification failed")
        return stdout.decode()

    def create_args(self, name: str, image: str, command: str, project: str) -> tuple[str, ...]:
        return (
            "create",
            "--name",
            name,
            "--interactive",
            "--read-only",
            "--network",
            "none",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--user",
            "10001:10001",
            "--pids-limit",
            "128",
            "--memory",
            "768m",
            "--memory-swap",
            "768m",
            "--cpus",
            "1",
            "--ulimit",
            "nofile=256:256",
            "--ulimit",
            "core=0:0",
            "--ipc",
            "private",
            "--log-driver",
            "none",
            "--tmpfs",
            "/workspace:rw,nosuid,nodev,size=64m,uid=10001,gid=10001,mode=0700",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,size=256m,uid=10001,gid=10001,mode=0700",
            "--entrypoint",
            "/opt/venv/bin/python",
            image,
            "-I",
            "/opt/runner/entrypoint.py",
            command,
            project,
        )

    @staticmethod
    def verify_container(info: dict) -> None:
        host, config = info["HostConfig"], info["Config"]
        if not (
            host["ReadonlyRootfs"]
            and host["NetworkMode"] == "none"
            and not host["Privileged"]
            and not host.get("Binds")
            and not info.get("Mounts")
            and not host.get("Devices")
            and host["CapDrop"] == ["ALL"]
            and not host.get("CapAdd")
            and "no-new-privileges:true" in host["SecurityOpt"]
            and host["PidsLimit"] == 128
            and host["Memory"] == 768 * 1024 * 1024
            and host["MemorySwap"] == host["Memory"]
            and host["NanoCpus"] == 1_000_000_000
            and host["PidMode"] == ""
            and host["IpcMode"] == "private"
            and config["User"] == "10001:10001"
            and set(host["Tmpfs"]) == {"/workspace", "/tmp"}
            and config["Entrypoint"] == ["/opt/venv/bin/python"]
        ):
            raise AgentToolDenied("Container isolation configuration rejected")

    async def run(
        self, workspace: Workspace, command: str, *, build: bool, project: str = "."
    ) -> CommandResult:
        argv = command_profile(command, build=build)
        if project != ".":
            validate_parts(project)
        archive, candidate_hash = workspace.archive()
        name = f"schwab-run-{uuid.uuid4().hex}"
        invocation = str(uuid.uuid4())
        started = datetime.now(UTC).isoformat()
        captured = bytearray()
        process = None
        error = None
        exit_code = None
        image_id = ""
        created = False
        try:
            image_id = (
                await self._docker("image", "inspect", "--format", "{{.Id}}", self.image)
            ).strip()
            if not image_id.startswith("sha256:"):
                raise AgentToolDenied("Runner image must resolve to an immutable ID")
            created = True
            await self._docker(*self.create_args(name, image_id, command, project))
            info = json.loads(await self._docker("inspect", name))[0]
            self.verify_container(info)
            process = await asyncio.create_subprocess_exec(
                "docker",
                "start",
                "--attach",
                "--interactive",
                name,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

            async def feed():
                try:
                    process.stdin.write(archive)
                    await process.stdin.drain()
                except (BrokenPipeError, ConnectionResetError):
                    pass
                finally:
                    process.stdin.close()

            async def drain():
                while chunk := await process.stdout.read(4096):
                    remaining = OUTPUT_LIMIT - len(captured)
                    captured.extend(chunk[:remaining])
                    if len(chunk) > remaining:
                        raise OutputLimit

            jobs = [
                asyncio.create_task(feed()),
                asyncio.create_task(drain()),
                asyncio.create_task(process.wait()),
            ]
            try:
                async with asyncio.timeout(self.timeout_seconds):
                    await asyncio.gather(*jobs)
                state = json.loads(
                    await self._docker("inspect", "--format", "{{json .State}}", name)
                )
                if state["Running"] or state["Status"] != "exited" or state.get("Error"):
                    raise AgentToolDenied("Candidate execution did not complete")
                exit_code = state["ExitCode"]
                if state.get("OOMKilled"):
                    error = "MEMORY_LIMIT"
                elif exit_code:
                    error = "COMMAND_FAILED"
            except TimeoutError:
                error = "TIMEOUT"
            except OutputLimit:
                error = "OUTPUT_LIMIT"
            finally:
                for job in jobs:
                    if not job.done():
                        job.cancel()
                await asyncio.gather(*jobs, return_exceptions=True)
        finally:
            # Destroy the container too; killing only the Docker client is insufficient.
            if created:
                await asyncio.shield(self._remove(name))
            if process is not None and process.returncode is None:
                process.kill()
                await process.wait()
        return CommandResult(
            invocation,
            str(workspace.workflow_id),
            argv,
            project,
            candidate_hash,
            image_id,
            started,
            datetime.now(UTC).isoformat(),
            exit_code,
            captured.decode(errors="replace"),
            error,
        )

    async def _remove(self, name):
        try:
            await self._docker("rm", "--force", "--volumes", name)
        except AgentToolDenied:
            # A cancelled/failed create may never have allocated a container.
            if await self._docker("ps", "-aq", "--filter", f"name=^{name}$"):
                raise
