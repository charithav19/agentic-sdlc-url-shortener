"""Explicit provider selection; real SDK is the application default."""

from collections.abc import Mapping
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.agents.fake_provider import FakeAgentProvider
from app.agents.openai_provider import OpenAIAgentProvider
from app.agents.provider import AgentProvider
from app.governance.policy import PolicyEngine


class AgentSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")
    agent_provider: Literal["openai", "fake"] = "openai"
    openai_model: str = ""
    openai_api_key: SecretStr = SecretStr("")


def create_agent_provider(
    settings: AgentSettings | None = None,
    *,
    fake_outputs: Mapping[str, object] | None = None,
    policy_engine: PolicyEngine | None = None,
) -> AgentProvider:
    settings = settings or AgentSettings()
    if settings.agent_provider == "fake":
        return FakeAgentProvider(fake_outputs or {})
    return OpenAIAgentProvider(
        model=settings.openai_model,
        api_key=settings.openai_api_key.get_secret_value(),
        policy_engine=policy_engine,
    )
