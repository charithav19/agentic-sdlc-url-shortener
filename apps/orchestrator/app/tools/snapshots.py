"""Allowlisted SDK tools over immutable input snapshots, with no host I/O."""

import json

from agents import FunctionTool, RunContextWrapper, function_tool

from app.agents.contracts import AgentContext, Specialist
from app.agents.errors import AgentToolDenied
from app.agents.provider import validate_request


def snapshot_tools(specialist: Specialist, context: AgentContext) -> list[FunctionTool]:
    validate_request(specialist, context)
    allowed = frozenset(context.authorized_tools)
    if not allowed <= {"read_artifact", "list_files", "read_file", "search_code"}:
        raise AgentToolDenied("Snapshot tools cannot perform engineering operations")

    def authorize(wrapper: RunContextWrapper[AgentContext], name: str) -> AgentContext:
        if wrapper.context != context or name not in allowed:
            raise AgentToolDenied("Tool is not authorized for this context")
        return wrapper.context

    @function_tool(failure_error_function=None)
    async def read_artifact(ctx: RunContextWrapper[AgentContext], name: str) -> str:
        """Read an exact versioned artifact supplied in this invocation's context."""
        inputs = authorize(ctx, "read_artifact")
        for artifact in inputs.artifacts:
            if artifact.name == name:
                return json.dumps({**artifact.model_dump(), "sha256": artifact.sha256})
        raise AgentToolDenied("Artifact not supplied")

    @function_tool(failure_error_function=None)
    async def list_files(ctx: RunContextWrapper[AgentContext]) -> list[str]:
        """List only code snapshot paths supplied for this invocation."""
        return [file.name for file in authorize(ctx, "list_files").files]

    @function_tool(failure_error_function=None)
    async def read_file(ctx: RunContextWrapper[AgentContext], path: str) -> str:
        """Read a supplied code snapshot; this never opens a host file."""
        for file in authorize(ctx, "read_file").files:
            if file.name == path:
                return file.content
        raise AgentToolDenied("File not supplied")

    @function_tool(failure_error_function=None)
    async def search_code(ctx: RunContextWrapper[AgentContext], text: str) -> list[str]:
        """Return at most 100 supplied snapshot lines matching a literal string."""
        inputs = authorize(ctx, "search_code")
        if not 1 <= len(text) <= 256:
            raise AgentToolDenied("Search text must contain 1–256 characters")
        results = []
        for file in inputs.files:
            for number, line in enumerate(file.content.splitlines(), 1):
                if text in line:
                    results.append(f"{file.name}:{number}: {line[:512]}")
                    if len(results) == 100:
                        return results
        return results

    registry = {tool.name: tool for tool in (read_artifact, list_files, read_file, search_code)}
    return [registry[name] for name in sorted(allowed)]
