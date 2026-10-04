"""Fixed profiles only. Neither arguments, environment nor executable are model-controlled."""

from types import MappingProxyType

from app.agents.errors import AgentToolDenied

COMMANDS = MappingProxyType(
    {
        "mvn test": ("mvn", "-o", "-B", "-Dmaven.repo.local=/tmp/m2", "test"),
        "mvn package": ("mvn", "-o", "-B", "-Dmaven.repo.local=/tmp/m2", "package"),
        "pytest": ("/opt/venv/bin/python", "-I", "-m", "pytest"),
    }
)


def command_profile(command: str, *, build: bool) -> tuple[str, ...]:
    permitted = {"mvn package"} if build else {"mvn test", "pytest"}
    if command not in permitted:
        raise AgentToolDenied("Command is not in the operation allowlist")
    return COMMANDS[command]
