"""Workflow-owned filesystem capabilities. Never resolve agent paths against cwd."""

import hashlib
import io
import os
import stat
import tarfile
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

from app.agents.errors import AgentToolDenied
from app.governance.policy import DEFAULT_POLICY_ENGINE, PolicyAction, PolicyInput, PolicyResult

MAX_FILE_BYTES = 256_000
MAX_WORKSPACE_BYTES = 8_000_000
MAX_FILES = 512
MAX_ENTRIES = 1024
MAX_DEPTH = 16
DENIED = {
    ".git",
    ".env",
    ".aws",
    ".ssh",
    ".docker",
    ".codex",
    ".kube",
    ".gnupg",
    ".azure",
    ".config",
    ".git-credentials",
    ".bash_history",
    "service-account.json",
    "service_account.json",
    "token.json",
    "tokens.json",
    "oauth.json",
    ".netrc",
    ".npmrc",
    ".pypirc",
    "credentials",
    "credentials.json",
    "secrets",
    "secrets.json",
    "settings.xml",
    "docker.sock",
    "id_rsa",
    "id_ed25519",
    "id_dsa",
    "id_ecdsa",
}


def validate_parts(path: str) -> tuple[str, ...]:
    value = PurePosixPath(path)
    parts = value.parts
    if (
        not path
        or value.is_absolute()
        or "\\" in path
        or ":" in path
        or any(ord(char) < 32 for char in path)
        or any(part in {".", "..", ""} for part in path.split("/"))
        or len(parts) > MAX_DEPTH
        or any(
            part.lower() in DENIED
            or part.lower().startswith((".env", "credentials", "secrets"))
            or part.lower().endswith((".pem", ".key", ".p12", ".pfx", ".keystore", ".sock"))
            for part in parts
        )
    ):
        raise AgentToolDenied("Forbidden workspace path")
    return parts


class WorkspaceManager:
    def __init__(self, root: Path | None = None):
        self.root = root or Path(__file__).resolve().parents[4] / "workspaces"
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.root.is_symlink():
            raise AgentToolDenied("Workspace root cannot be a symlink")
        self.root = self.root.resolve()

    def for_workflow(self, workflow_id: uuid.UUID) -> "Workspace":
        if not isinstance(workflow_id, uuid.UUID):
            raise AgentToolDenied("A workflow UUID is required")
        with self._root_fd() as root_fd:
            try:
                os.mkdir(str(workflow_id), mode=0o700, dir_fd=root_fd)
            except FileExistsError:
                pass
            try:
                fd = os.open(
                    str(workflow_id),
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=root_fd,
                )
            except OSError:
                raise AgentToolDenied("Unsafe workflow directory") from None
        return Workspace(self.root / str(workflow_id), workflow_id, fd)

    @contextmanager
    def _root_fd(self):
        fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            yield fd
        finally:
            os.close(fd)


class Workspace:
    def __init__(self, path: Path, workflow_id: uuid.UUID, fd: int):
        self.path, self.workflow_id, self._fd = path, workflow_id, fd
        self._lock = threading.RLock()

    def close(self):
        if self._fd >= 0:
            os.close(self._fd)
            self._fd = -1

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _parts(self, path: str) -> tuple[str, ...]:
        # Reject traversal even when an absolute spelling would normalize inside.
        if ".." in path.split("/"):
            raise AgentToolDenied("Traversal is forbidden")
        candidate = Path(path)
        if candidate.is_absolute():
            try:
                path = candidate.relative_to(self.path).as_posix()
            except ValueError:
                raise AgentToolDenied("Path outside workflow workspace") from None
        return validate_parts(path)

    @contextmanager
    def _parent(self, path: str, *, create: bool = False):
        parts = self._parts(path)
        fd = os.dup(self._fd)
        try:
            for part in parts[:-1]:
                if create:
                    try:
                        os.mkdir(part, mode=0o700, dir_fd=fd)
                    except FileExistsError:
                        pass
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = child
            yield fd, parts[-1]
        except OSError:
            raise AgentToolDenied("Unsafe or missing workspace path") from None
        finally:
            os.close(fd)

    def read_bytes(self, path: str) -> bytes:
        with self._lock, self._parent(path) as (parent, name):
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
            try:
                info = os.fstat(fd)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise AgentToolDenied("Only single-link regular files are allowed")
                with os.fdopen(fd, "rb", closefd=False) as stream:
                    data = stream.read(MAX_FILE_BYTES + 1)
                if len(data) > MAX_FILE_BYTES:
                    raise AgentToolDenied("File size limit exceeded")
                return data
            finally:
                os.close(fd)

    def read_file(self, path: str) -> str:
        try:
            return self.read_bytes(path).decode("utf-8")
        except UnicodeDecodeError:
            raise AgentToolDenied("Text tools require UTF-8") from None

    def list_files(self) -> list[str]:
        result: list[str] = []
        entries = 0

        def walk(fd, prefix, depth):
            nonlocal entries
            if depth > MAX_DEPTH:
                raise AgentToolDenied("Workspace depth limit exceeded")
            names = []
            with os.scandir(fd) as iterator:
                for entry in iterator:
                    entries += 1
                    if entries > MAX_ENTRIES:
                        raise AgentToolDenied("Workspace entry limit exceeded")
                    names.append(entry.name)
            for name in sorted(names):
                relative = f"{prefix}/{name}" if prefix else name
                try:
                    validate_parts(relative)
                except AgentToolDenied:
                    continue
                info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                if stat.S_ISDIR(info.st_mode):
                    child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                    try:
                        walk(child, relative, depth + 1)
                    finally:
                        os.close(child)
                elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                    result.append(relative)
                    if len(result) > MAX_FILES:
                        raise AgentToolDenied("Workspace file count exceeded")
                # Symlinks, hardlinks, sockets and FIFOs are never exposed or archived.

        with self._lock:
            try:
                walk(self._fd, "", 0)
            except OSError:
                raise AgentToolDenied("Workspace changed during traversal") from None
        return result

    def write_file(self, path: str, content: str) -> dict[str, str]:
        decision = DEFAULT_POLICY_ENGINE.evaluate(
            PolicyInput(
                action=PolicyAction.WRITE_FILE.value,
                actor_type="AGENT",
                actor_id="workspace-tool",
                workspace_root=str(self.path),
                target_path=path,
                content=content,
            )
        )
        if decision.result is not PolicyResult.ALLOW:
            raise AgentToolDenied(decision.decisive_finding.reason)
        data = content.encode("utf-8")
        if len(data) > MAX_FILE_BYTES:
            raise AgentToolDenied("File size limit exceeded")
        with self._lock:
            names = self.list_files()
            canonical = "/".join(self._parts(path))
            total = sum(len(self.read_bytes(name)) for name in names if name != canonical)
            if total + len(data) > MAX_WORKSPACE_BYTES:
                raise AgentToolDenied("Workspace size limit exceeded")
            if canonical not in names and len(names) >= MAX_FILES:
                raise AgentToolDenied("Workspace file count exceeded")
            with self._parent(path, create=True) as (parent, name):
                try:
                    info = os.stat(name, dir_fd=parent, follow_symlinks=False)
                    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                        raise AgentToolDenied("Unsafe write target")
                    created = False
                except FileNotFoundError:
                    created = True
                temp = f".edit-{uuid.uuid4().hex}"
                fd = os.open(
                    temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent
                )
                try:
                    with os.fdopen(fd, "wb") as stream:
                        stream.write(data)
                    os.replace(temp, name, src_dir_fd=parent, dst_dir_fd=parent)
                finally:
                    try:
                        os.unlink(temp, dir_fd=parent)
                    except FileNotFoundError:
                        pass
            return {
                "path": canonical,
                "action": "created" if created else "changed",
                "sha256": hashlib.sha256(data).hexdigest(),
            }

    def apply_patch(self, path: str, old_text: str, new_text: str) -> dict[str, str]:
        """One exact replacement; refuses ambiguous or stale patches."""
        with self._lock:
            content = self.read_file(path)
            if not old_text or content.count(old_text) != 1:
                raise AgentToolDenied("Patch must match exactly once")
            return self.write_file(path, content.replace(old_text, new_text, 1))

    def search_code(self, text: str) -> list[str]:
        if not 1 <= len(text) <= 256:
            raise AgentToolDenied("Search text must contain 1–256 characters")
        results = []
        total = 0
        for name in self.list_files():
            data = self.read_bytes(name)
            total += len(data)
            if total > MAX_WORKSPACE_BYTES:
                raise AgentToolDenied("Workspace size limit exceeded")
            try:
                content = data.decode("utf-8")
            except UnicodeDecodeError:
                continue
            for number, line in enumerate(content.splitlines(), 1):
                if text in line:
                    results.append(f"{name}:{number}: {line[:512]}")
                    if len(results) == 100:
                        return results
        return results

    def archive(self) -> tuple[bytes, str]:
        """Fresh regular-file-only snapshot for an isolated command invocation."""
        with self._lock:
            output = io.BytesIO()
            total = 0
            with tarfile.open(fileobj=output, mode="w") as archive:
                for name in self.list_files():
                    data = self.read_bytes(name)
                    total += len(data)
                    if total > MAX_WORKSPACE_BYTES:
                        raise AgentToolDenied("Workspace size limit exceeded")
                    info = tarfile.TarInfo(name)
                    info.size, info.mode = len(data), 0o600
                    archive.addfile(info, io.BytesIO(data))
            data = output.getvalue()
            return data, hashlib.sha256(data).hexdigest()
