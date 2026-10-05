"""Requirement-analysis runner and immutable clarification contracts."""

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.agents.contracts import AgentContext
from app.agents.provider import AgentProvider
from app.agents.requirement import RequirementAgent
from app.orchestration.commands import TransitionContext
from app.orchestration.contracts import StageStatus, WorkflowStatus

if TYPE_CHECKING:
    from app.orchestration.orchestrator import WorkflowOrchestrator


@dataclass(frozen=True)
class RequirementAnalysisResult:
    workflow_id: uuid.UUID
    workflow_status: WorkflowStatus
    workflow_version: int
    analysis_artifact_id: uuid.UUID
    analysis_artifact_version: int
    clarification_artifact_id: uuid.UUID | None
    clarification_artifact_version: int | None
    blocking_ambiguity: bool
    questions: tuple[str, ...]


@dataclass(frozen=True)
class ClarificationSubmissionResult:
    workflow_id: uuid.UUID
    workflow_status: WorkflowStatus
    workflow_version: int
    generation: int
    clarification_artifact_id: uuid.UUID
    clarification_artifact_version: int
    requirement_artifact_id: uuid.UUID
    requirement_version: int
    requirement_analysis_stage_run_id: uuid.UUID


class RequirementAnalysisRunner:
    """Invoke the agent without giving it workflow mutation authority."""

    def __init__(self, orchestrator: "WorkflowOrchestrator", provider: AgentProvider) -> None:
        self.orchestrator = orchestrator
        self.provider = provider

    async def run(
        self,
        *,
        requirement_artifact_id: uuid.UUID,
        agent_context: AgentContext,
        transition_context: TransitionContext,
    ) -> RequirementAnalysisResult:
        await self.orchestrator.transition_stage(
            agent_context.stage_run_id,
            target=StageStatus.RUNNING,
            context=transition_context,
        )
        result = await self.provider.run(RequirementAgent(), agent_context)
        return await self.orchestrator.record_requirement_analysis(
            agent_context.workflow_id,
            requirement_artifact_id=requirement_artifact_id,
            result=result,
            context=transition_context,
        )
