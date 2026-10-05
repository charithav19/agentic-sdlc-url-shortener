"""Primary runtime: the pinned OpenAI Agents SDK Agent and Runner."""

import asyncio

from agents import Agent, ModelSettings, RunConfig, Runner
from agents.exceptions import MaxTurnsExceeded, ModelBehaviorError
from agents.models.openai_provider import OpenAIProvider
from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI, RateLimitError
from pydantic import BaseModel

from app.agents.contracts import AgentContext, AgentResult, Specialist
from app.agents.errors import (
    AgentBudgetExceeded,
    AgentConfigurationError,
    AgentOutputError,
    AgentProviderError,
    AgentTimeout,
    AgentTransientError,
)
from app.agents.provider import AgentProvider, validate_request, validated_result
from app.governance.policy import PolicyEngine
from app.tools.engineering import engineering_tools
from app.tools.runner import DockerRunner
from app.tools.workspaces import Workspace, WorkspaceManager


class OpenAIAgentProvider(AgentProvider):
    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        workspaces: WorkspaceManager | None = None,
        runner: DockerRunner | None = None,
        policy_engine: PolicyEngine | None = None,
    ) -> None:
        if not model.strip() or not api_key.strip():
            raise AgentConfigurationError("OPENAI_MODEL and OPENAI_API_KEY are required")
        self.model = model
        self._api_key = api_key
        self.workspaces = workspaces or WorkspaceManager()
        self.runner = runner or DockerRunner()
        self.policy_engine = policy_engine

    async def run[T: BaseModel](
        self, specialist: Specialist[T], context: AgentContext
    ) -> AgentResult[T]:
        validate_request(specialist, context)
        with self.workspaces.for_workflow(context.workflow_id) as workspace:
            return await self._run(specialist, context, workspace)

    async def _run[T: BaseModel](
        self, specialist: Specialist[T], context: AgentContext, workspace: Workspace
    ) -> AgentResult[T]:
        receipts = []
        agent = Agent[AgentContext](
            name=specialist.name,
            instructions=specialist.instructions,
            output_type=specialist.output_type,
            tools=engineering_tools(
                specialist,
                context,
                workspace,
                self.runner,
                receipts,
                policy_engine=self.policy_engine,
            ),
            handoffs=[],
            mcp_servers=[],
            model=self.model,
            model_settings=ModelSettings(parallel_tool_calls=False, max_tokens=8192),
        )
        try:
            async with asyncio.timeout(specialist.timeout_seconds):
                async with AsyncOpenAI(
                    api_key=self._api_key,
                    base_url="https://api.openai.com/v1",
                    max_retries=0,
                    timeout=specialist.timeout_seconds,
                ) as client:
                    result = await Runner.run(
                        agent,
                        input=context.model_dump_json(),
                        context=context,
                        max_turns=specialist.max_turns,
                        run_config=RunConfig(
                            model_provider=OpenAIProvider(openai_client=client, use_responses=True),
                            tracing_disabled=True,
                            trace_include_sensitive_data=False,
                            workflow_name=specialist.name,
                            tool_not_found_behavior="raise_error",
                        ),
                    )
            output = validated_result(
                specialist, context, result.final_output, provider="openai", model=self.model
            )
            return output.model_copy(update={"tool_receipts": tuple(receipts)})
        except MaxTurnsExceeded:
            raise AgentBudgetExceeded("Agent exhausted its turn budget") from None
        except (TimeoutError, APITimeoutError):
            raise AgentTimeout("Agent exceeded its time budget") from None
        except ModelBehaviorError:
            raise AgentOutputError("SDK rejected model output or an unknown tool call") from None
        except (RateLimitError, APIConnectionError):
            raise AgentTransientError("Temporary provider failure") from None
        except APIStatusError as error:
            if error.status_code >= 500:
                raise AgentTransientError("Temporary provider failure") from None
            raise AgentProviderError("Provider rejected the request") from None
