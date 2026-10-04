"""Explicit fixture playback. No model/network, tools, state writes or success fallback."""

import json
from collections.abc import Mapping

from pydantic import BaseModel

from app.agents.contracts import AgentContext, AgentResult, Specialist
from app.agents.errors import AgentConfigurationError
from app.agents.provider import AgentProvider, validate_request, validated_result


class FakeAgentProvider(AgentProvider):
    def __init__(self, outputs: Mapping[str, object]) -> None:
        self._outputs = json.dumps(dict(outputs), sort_keys=True)

    async def run[T: BaseModel](
        self, specialist: Specialist[T], context: AgentContext
    ) -> AgentResult[T]:
        validate_request(specialist, context)
        outputs = json.loads(self._outputs)
        if specialist.name not in outputs:
            raise AgentConfigurationError(f"No fake fixture for {specialist.name}")
        return validated_result(
            specialist, context, outputs[specialist.name], provider="fake", model="fixture-v1"
        )
