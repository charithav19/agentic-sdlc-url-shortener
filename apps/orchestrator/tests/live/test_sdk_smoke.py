"""Opt-in live evidence; never a prerequisite for ordinary CI."""

import os

import pytest

from app.agents.requirement import RequirementAgent
from app.agents.settings import AgentSettings, create_agent_provider


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_requirement_sdk_smoke(agent_context):
    if os.environ.get("RUN_LIVE_AGENT_TESTS") != "1":
        pytest.skip("Live SDK smoke is opt-in: RUN_LIVE_AGENT_TESTS=1")
    settings = AgentSettings(agent_provider="openai")
    if not settings.openai_api_key.get_secret_value() or not settings.openai_model:
        pytest.fail("Live smoke requires OPENAI_API_KEY and OPENAI_MODEL")
    result = await create_agent_provider(settings).run(RequirementAgent(), agent_context)
    assert result.provider == "openai"
    assert result.output.normalized_requirement
    assert result.output.acceptance_criteria
    assert result.model == settings.openai_model
