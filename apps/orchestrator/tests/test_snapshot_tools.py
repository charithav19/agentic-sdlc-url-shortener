"""Snapshot tools cannot reach host paths or other invocation contexts."""

import json

import pytest
from agents.tool_context import ToolContext
from pydantic import ValidationError

from app.agents.contracts import FileSnapshot
from app.agents.errors import AgentToolDenied
from app.agents.implementation import ImplementationAgent
from app.agents.requirement import RequirementAgent
from app.tools.snapshots import snapshot_tools


def tool_context(context, name="read_artifact"):
    return ToolContext(
        context=context, tool_name=name, tool_call_id="test-call", tool_arguments="{}"
    )


@pytest.mark.asyncio
async def test_snapshot_reads_and_search_are_bounded(agent_context):
    context = agent_context.model_copy(
        update={
            "authorized_tools": ("read_file", "list_files", "search_code"),
        }
    )
    tools = {tool.name: tool for tool in snapshot_tools(ImplementationAgent(), context)}
    wrapper = tool_context(context)
    assert await tools["list_files"].on_invoke_tool(wrapper, "{}") == ["src/app.py"]
    assert (
        await tools["read_file"].on_invoke_tool(wrapper, json.dumps({"path": "src/app.py"}))
        == "return 302"
    )
    assert await tools["search_code"].on_invoke_tool(wrapper, json.dumps({"text": "302"})) == [
        "src/app.py:1: return 302"
    ]
    with pytest.raises(AgentToolDenied):
        await tools["read_file"].on_invoke_tool(wrapper, '{"path": "/etc/passwd"}')
    with pytest.raises(AgentToolDenied):
        await tools["search_code"].on_invoke_tool(wrapper, '{"text": ""}')


@pytest.mark.asyncio
async def test_tool_cannot_switch_context_or_read_unsupplied_artifact(agent_context):
    context = agent_context.model_copy(update={"authorized_tools": ("read_artifact",)})
    tool = snapshot_tools(RequirementAgent(), context)[0]
    with pytest.raises(AgentToolDenied):
        await tool.on_invoke_tool(tool_context(agent_context), '{"name": "requirement-v1"}')
    with pytest.raises(AgentToolDenied):
        await tool.on_invoke_tool(tool_context(context), '{"name": "other"}')


@pytest.mark.parametrize("path", ["/etc/passwd", "../secret", "a/../../secret", ".env", ".aws/key"])
def test_secret_and_host_paths_rejected(path):
    with pytest.raises(ValidationError):
        FileSnapshot(name=path, version=1, content="text")


def test_context_has_no_mutable_state_or_unbounded_input(agent_context):
    with pytest.raises(ValidationError):
        agent_context.requirement = "mutated"
    with pytest.raises(ValidationError):
        type(agent_context).model_validate(
            {
                **agent_context.model_dump(),
                "status": "COMPLETED",
            }
        )
    with pytest.raises(ValidationError):
        type(agent_context).model_validate(
            {
                **agent_context.model_dump(),
                "files": [FileSnapshot(name="big.py", version=1, content="x" * 64001)],
            }
        )
