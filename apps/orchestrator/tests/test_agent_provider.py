"""Default fixture provider and real SDK loop tests without network calls."""

import asyncio
import copy
import json
from dataclasses import replace
from types import SimpleNamespace

import httpx
import pytest
from agents import Model, ModelResponse, Runner
from agents.models.openai_provider import OpenAIProvider
from agents.usage import Usage
from openai import APIConnectionError, APIStatusError, RateLimitError
from openai.types.responses import (
    ResponseFunctionToolCall,
    ResponseOutputMessage,
    ResponseOutputText,
)

from app.agents.contracts import Specialist
from app.agents.errors import (
    AgentBudgetExceeded,
    AgentConfigurationError,
    AgentOutputError,
    AgentProviderError,
    AgentTimeout,
    AgentToolDenied,
    AgentTransientError,
)
from app.agents.fake_provider import FakeAgentProvider
from app.agents.openai_provider import OpenAIAgentProvider
from app.agents.registry import SPECIALISTS
from app.agents.requirement import RequirementAgent
from app.agents.settings import AgentSettings, create_agent_provider
from tests.agent_fixtures import OUTPUTS


@pytest.fixture(autouse=True)
def deny_network(monkeypatch):
    async def denied(*args, **kwargs):
        raise AssertionError("Offline provider tests must not send network requests")

    monkeypatch.setattr(httpx.AsyncClient, "send", denied)


@pytest.mark.asyncio
@pytest.mark.parametrize("specialist", SPECIALISTS.values(), ids=lambda item: item.name)
async def test_fake_provider_repeatable_and_validated(agent_provider, agent_context, specialist):
    first = await agent_provider.run(specialist, agent_context)
    second = await agent_provider.run(specialist, agent_context)
    assert first == second
    assert first.provider == "fake"
    assert isinstance(first.output, specialist.output_type)
    assert first.trace_id == agent_context.trace_id
    assert len(first.context_sha256) == 64
    assert first.sdk_version == "0.23.1"


@pytest.mark.asyncio
async def test_fake_fixture_and_result_are_defensively_copied(agent_context):
    fixture = copy.deepcopy(OUTPUTS)
    provider = FakeAgentProvider(fixture)
    fixture["RequirementAgent"]["risks"].clear()
    result = await provider.run(RequirementAgent(), agent_context)
    result.output.risks.clear()
    again = await provider.run(RequirementAgent(), agent_context)
    assert again.output.risks == OUTPUTS["RequirementAgent"]["risks"]


@pytest.mark.asyncio
async def test_fake_missing_and_malformed_output_fail(agent_context):
    with pytest.raises(AgentConfigurationError, match="No fake fixture"):
        await FakeAgentProvider({}).run(RequirementAgent(), agent_context)
    with pytest.raises(AgentOutputError):
        await FakeAgentProvider({"RequirementAgent": {"status": "COMPLETED"}}).run(
            RequirementAgent(), agent_context
        )


def test_default_provider_is_real_sdk(monkeypatch):
    monkeypatch.delenv("AGENT_PROVIDER", raising=False)
    settings = AgentSettings(openai_api_key="test-key", openai_model="test-model")
    assert settings.agent_provider == "openai"
    assert isinstance(create_agent_provider(settings), OpenAIAgentProvider)
    assert isinstance(
        create_agent_provider(AgentSettings(agent_provider="fake")), FakeAgentProvider
    )
    with pytest.raises(AgentConfigurationError):
        create_agent_provider(AgentSettings(openai_api_key="", openai_model=""))
    assert "test-key" not in repr(settings)


class ScriptedModel(Model):
    """Exercises actual SDK parsing and tools while replacing only network inference."""

    def __init__(self, *, tool_name=None, forever=False, malformed=False):
        self.calls = []
        self.tool_name = tool_name
        self.forever = forever
        self.malformed = malformed

    async def get_response(self, *args, **kwargs):
        self.calls.append(kwargs)
        if self.tool_name and (len(self.calls) == 1 or self.forever):
            output = [
                ResponseFunctionToolCall(
                    type="function_call",
                    name=self.tool_name,
                    call_id=f"call_{len(self.calls)}",
                    arguments=json.dumps({"name": "requirement-v1"}),
                )
            ]
        else:
            output = [
                ResponseOutputMessage(
                    id="message-1",
                    type="message",
                    role="assistant",
                    status="completed",
                    content=[
                        ResponseOutputText(
                            type="output_text",
                            text=json.dumps(
                                {"status": "COMPLETED"}
                                if self.malformed
                                else OUTPUTS["RequirementAgent"]
                            ),
                            annotations=[],
                        )
                    ],
                )
            ]
        return ModelResponse(output=output, usage=Usage(requests=1), response_id="local")

    async def stream_response(self, *args, **kwargs):
        raise NotImplementedError("Streaming is not used")
        yield  # pragma: no cover


@pytest.mark.asyncio
async def test_real_sdk_loop_parses_schema_and_calls_only_authorized_tool(
    monkeypatch, agent_context
):
    model = ScriptedModel(tool_name="read_artifact")
    monkeypatch.setattr(OpenAIProvider, "get_model", lambda self, name: model)
    context = agent_context.model_copy(update={"authorized_tools": ("read_artifact",)})
    result = await OpenAIAgentProvider(model="test-model", api_key="test-key").run(
        RequirementAgent(), context
    )
    assert result.provider == "openai"
    assert (
        result.output.normalized_requirement
        == OUTPUTS["RequirementAgent"]["normalized_requirement"]
    )
    assert len(model.calls) == 2
    assert [tool.name for tool in model.calls[0]["tools"]] == ["read_artifact"]
    assert model.calls[0]["handoffs"] == []
    assert any(
        item.get("type") == "function_call_output" and "sha256" in item["output"]
        for item in model.calls[1]["input"]
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("model", "expected"),
    [
        (ScriptedModel(tool_name="read_artifact", forever=True), AgentBudgetExceeded),
        (ScriptedModel(malformed=True), AgentOutputError),
        (ScriptedModel(tool_name="change_workflow_status"), AgentOutputError),
    ],
)
async def test_sdk_failure_paths(monkeypatch, agent_context, model, expected):
    monkeypatch.setattr(OpenAIProvider, "get_model", lambda self, name: model)
    context = agent_context.model_copy(update={"authorized_tools": ("read_artifact",)})
    with pytest.raises(expected):
        await OpenAIAgentProvider(model="test-model", api_key="test-key").run(
            replace(Specialist(**vars(RequirementAgent())), max_turns=2), context
        )


@pytest.mark.asyncio
async def test_timeout_and_cancellation_propagate(monkeypatch, agent_context):
    started = asyncio.Event()

    async def wait_forever(*args, **kwargs):
        started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(Runner, "run", wait_forever)
    provider = OpenAIAgentProvider(model="test-model", api_key="test-key")
    with pytest.raises(AgentTimeout):
        await provider.run(
            replace(Specialist(**vars(RequirementAgent())), timeout_seconds=0.01), agent_context
        )
    started.clear()
    task = asyncio.create_task(provider.run(RequirementAgent(), agent_context))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_runtime_revalidates_final_output(monkeypatch, agent_context):
    async def malformed(*args, **kwargs):
        return SimpleNamespace(final_output={"status": "COMPLETED"})

    monkeypatch.setattr(Runner, "run", malformed)
    with pytest.raises(AgentOutputError):
        await OpenAIAgentProvider(model="test-model", api_key="test-key").run(
            RequirementAgent(), agent_context
        )


@pytest.mark.asyncio
async def test_both_providers_deny_excess_tools(agent_context):
    context = agent_context.model_copy(update={"authorized_tools": ("read_file",)})
    for provider in (
        FakeAgentProvider(OUTPUTS),
        OpenAIAgentProvider(model="test-model", api_key="test-key"),
    ):
        with pytest.raises(AgentToolDenied):
            await provider.run(RequirementAgent(), context)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "expected"),
    [(429, AgentTransientError), (503, AgentTransientError), (401, AgentProviderError)],
)
async def test_provider_classifies_http_errors_without_retry(
    monkeypatch, agent_context, status_code, expected
):
    calls = 0

    async def fail(*args, **kwargs):
        nonlocal calls
        calls += 1
        response = httpx.Response(
            status_code, request=httpx.Request("POST", "https://example.test")
        )
        error_type = RateLimitError if status_code == 429 else APIStatusError
        raise error_type("sensitive raw provider message", response=response, body=None)

    monkeypatch.setattr(Runner, "run", fail)
    with pytest.raises(expected) as error:
        await OpenAIAgentProvider(model="test-model", api_key="test-key").run(
            RequirementAgent(), agent_context
        )
    assert calls == 1
    assert "sensitive" not in str(error.value)
    assert error.value.retryable is (status_code != 401)


@pytest.mark.asyncio
async def test_network_failure_is_classified(monkeypatch, agent_context):
    async def fail(*args, **kwargs):
        raise APIConnectionError(request=httpx.Request("POST", "https://example.test"))

    monkeypatch.setattr(Runner, "run", fail)
    with pytest.raises(AgentTransientError):
        await OpenAIAgentProvider(model="test-model", api_key="test-key").run(
            RequirementAgent(), agent_context
        )
