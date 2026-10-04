"""Trusted container entry point. Candidate input is regular files, never argv or env."""

import io
import os
import shutil
import sys
import tarfile
from pathlib import Path

COMMANDS = {
    "mvn test": ("/usr/share/maven/bin/mvn", "-o", "-B", "-Dmaven.repo.local=/tmp/m2", "test"),
    "mvn package": (
        "/usr/share/maven/bin/mvn",
        "-o",
        "-B",
        "-Dmaven.repo.local=/tmp/m2",
        "package",
    ),
    "pytest": ("/opt/venv/bin/python", "-I", "-m", "pytest"),
}


def main():
    command, project = sys.argv[1:]
    if command not in COMMANDS:
        raise ValueError("Unknown command")
    root = Path("/workspace")
    target = root / project
    if not target.resolve().is_relative_to(root) or ".." in Path(project).parts:
        raise ValueError("Invalid project")
    data = sys.stdin.buffer.read(10_000_001)
    if len(data) > 10_000_000:
        raise ValueError("Archive too large")
    total = 0
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as archive:
        for index, member in enumerate(archive):
            if index >= 512 or not member.isfile() or member.size > 256_000:
                raise ValueError("Unsafe archive member")
            path = root / member.name
            if not path.resolve().is_relative_to(root) or ".." in Path(member.name).parts:
                raise ValueError("Unsafe archive path")
            total += member.size
            if total > 8_000_000:
                raise ValueError("Archive too large")
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as output:
                output.write(archive.extractfile(member).read())
    if command.startswith("mvn"):
        shutil.copytree("/opt/maven-repository", "/tmp/m2")
    Path("/tmp/home").mkdir(exist_ok=True)
    os.chdir(target)
    os.execve(
        COMMANDS[command][0],
        COMMANDS[command],
        {
            "PATH": "/opt/venv/bin:/usr/share/maven/bin:/opt/java/openjdk/bin:/usr/bin:/bin",
            "JAVA_HOME": "/opt/java/openjdk",
            "HOME": "/tmp/home",
            "LANG": "C.UTF-8",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        },
    )


if __name__ == "__main__":
    main()
