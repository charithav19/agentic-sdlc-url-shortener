"""SDK bindings to a single trusted workflow workspace and fixed command runner."""

from agents import FunctionTool, RunContextWrapper, function_tool

from app.agents.contracts import AgentContext, Specialist
from app.agents.errors import AgentToolDenied
from app.agents.provider import validate_request
from app.tools.runner import DockerRunner
from app.tools.workspaces import Workspace


def engineering_tools(
    specialist: Specialist,
    context: AgentContext,
    workspace: Workspace,
    runner: DockerRunner,
    receipts: list[dict],
) -> list[FunctionTool]:
    validate_request(specialist, context)
    if workspace.workflow_id != context.workflow_id:
        raise AgentToolDenied("Workspace belongs to another workflow")
    allowed = frozenset(context.authorized_tools)

    def authorize(ctx, name):
        if ctx.context != context or name not in allowed:
            raise AgentToolDenied("Tool not authorized for this invocation")

    @function_tool(failure_error_function=None)
    async def list_files(ctx: RunContextWrapper[AgentContext]) -> list[str]:
        """List non-secret regular files in this workflow's workspace."""
        authorize(ctx, "list_files")
        return workspace.list_files()

    @function_tool(failure_error_function=None)
    async def read_file(ctx: RunContextWrapper[AgentContext], path: str) -> str:
        """Read a bounded UTF-8 file in this workflow's workspace."""
        authorize(ctx, "read_file")
        return workspace.read_file(path)

    @function_tool(failure_error_function=None)
    async def search_code(ctx: RunContextWrapper[AgentContext], text: str) -> list[str]:
        """Search literal text in this workspace, returning at most 100 matching lines."""
        authorize(ctx, "search_code")
        return workspace.search_code(text)

    @function_tool(failure_error_function=None)
    async def write_file(ctx: RunContextWrapper[AgentContext], path: str, content: str) -> dict:
        """Create or replace a bounded UTF-8 workspace file. Returns a file hash receipt."""
        authorize(ctx, "write_file")
        result = workspace.write_file(path, content)
        receipts.append({"tool": "write_file", **result})
        return result

    @function_tool(failure_error_function=None)
    async def apply_patch(
        ctx: RunContextWrapper[AgentContext], path: str, old_text: str, new_text: str
    ) -> dict:
        """Replace one exact unique occurrence in a workspace file; stale/ambiguous matches fail."""
        authorize(ctx, "apply_patch")
        result = workspace.apply_patch(path, old_text, new_text)
        receipts.append({"tool": "apply_patch", **result})
        return result

    @function_tool(failure_error_function=None)
    async def run_build(ctx: RunContextWrapper[AgentContext], command: str, project: str) -> dict:
        """Run only 'mvn package'. Project is a workspace-relative directory or '.'."""
        authorize(ctx, "run_build")
        result = (await runner.run(workspace, command, build=True, project=project)).as_dict()
        receipts.append({"tool": "run_build", **result})
        return result

    @function_tool(failure_error_function=None)
    async def run_tests(ctx: RunContextWrapper[AgentContext], command: str, project: str) -> dict:
        """Run only 'mvn test' or 'pytest' in an isolated snapshot, never arbitrary shell."""
        authorize(ctx, "run_tests")
        result = (await runner.run(workspace, command, build=False, project=project)).as_dict()
        receipts.append({"tool": "run_tests", **result})
        return result

    registry = {
        tool.name: tool
        for tool in (
            list_files,
            read_file,
            search_code,
            write_file,
            apply_patch,
            run_build,
            run_tests,
        )
    }
    if "read_artifact" in allowed:

        @function_tool(name_override="read_artifact", failure_error_function=None)
        async def read_artifact(ctx: RunContextWrapper[AgentContext], name: str) -> str:
            """Read an exact supplied artifact, never a database or workflow object."""
            import json

            authorize(ctx, "read_artifact")
            for artifact in context.artifacts:
                if artifact.name == name:
                    return json.dumps({**artifact.model_dump(), "sha256": artifact.sha256})
            raise AgentToolDenied("Artifact not supplied")

        registry["read_artifact"] = read_artifact
    return [registry[name] for name in sorted(allowed)]
