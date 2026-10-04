"""Provider boundary shared by live SDK and deterministic fixture implementations."""

from abc import ABC, abstractmethod
from importlib.metadata import version
from math import isfinite

from pydantic import BaseModel, ValidationError

from app.agents.contracts import AgentContext, AgentResult, Specialist, digest
from app.agents.errors import AgentConfigurationError, AgentOutputError, AgentToolDenied


def validate_request(specialist: Specialist, context: AgentContext) -> None:
    if (
        specialist.max_turns < 1
        or specialist.timeout_seconds <= 0
        or not isfinite(specialist.timeout_seconds)
    ):
        raise AgentConfigurationError("Agent budgets must be positive")
    if not set(context.authorized_tools) <= set(specialist.allowed_tools):
        raise AgentToolDenied("Requested tools exceed the specialist allowlist")


def validated_result[T: BaseModel](
    specialist: Specialist[T], context: AgentContext, raw: object, *, provider: str, model: str
) -> AgentResult[T]:
    try:
        if isinstance(raw, BaseModel):
            raw = raw.model_dump(mode="python")
        output = specialist.output_type.model_validate(raw)
    except ValidationError:
        raise AgentOutputError("Specialist output does not satisfy its schema") from None
    return AgentResult(
        output=output,
        provider=provider,
        model=model,
        sdk_version=version("openai-agents"),
        specialist=specialist.name,
        instruction_version=specialist.instruction_version,
        schema_version=specialist.schema_version,
        instruction_sha256=digest(specialist.instructions),
        schema_sha256=digest(specialist.output_type.model_json_schema()),
        context_sha256=digest(context.model_dump(mode="json")),
        workflow_id=context.workflow_id,
        stage_run_id=context.stage_run_id,
        trace_id=context.trace_id,
        generation=context.generation,
        attempt=context.attempt,
        max_turns=specialist.max_turns,
        timeout_seconds=specialist.timeout_seconds,
    )


class AgentProvider(ABC):
    @abstractmethod
    async def run[T: BaseModel](
        self, specialist: Specialist[T], context: AgentContext
    ) -> AgentResult[T]:
        """Return validated output; never accept a session, ORM entity or state callback."""
