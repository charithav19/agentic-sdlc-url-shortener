"""Application runtime binding the existing scheduler, specialists, and human checkpoints."""

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from app.agents.contracts import AgentContext, FileSnapshot, Snapshot
from app.agents.errors import AgentConfigurationError
from app.agents.fake_provider import FakeAgentProvider
from app.agents.openai_provider import OpenAIAgentProvider
from app.agents.registry import SPECIALISTS
from app.agents.settings import AgentSettings
from app.artifacts.schemas import ArtifactInput
from app.artifacts.store import canonical_content
from app.config import Settings
from app.governance.approvals import ApprovalStatus, ApprovalType
from app.governance.policy import PolicyEngine
from app.orchestration.claims import StageClaim, StageCompletion
from app.orchestration.commands import TransitionContext
from app.orchestration.contracts import StageStatus, WorkflowStatus
from app.orchestration.evidence_validation import (
    ApprovalEvidence,
    ArtifactEvidence,
    GateContext,
    StageEvidence,
)
from app.orchestration.failure_classifier import (
    FailedTestAssertion,
    InvalidWorkflowStateFailure,
    SecurityViolationFailure,
)
from app.orchestration.gates import (
    ArchitectureEntryGate,
    ArchitectureExitGate,
    GateResult,
    ImplementationEntryGate,
    ReleaseReadinessEntryGate,
    RequirementExitGate,
)
from app.orchestration.orchestrator import WorkflowOrchestrator
from app.orchestration.scheduler import WorkflowScheduler
from app.orchestration.workflows import WorkflowService
from app.persistence.models import Approval, Artifact, StageRun, WorkflowRun
from app.persistence.service import WorkflowPersistenceService
from app.persistence.session import session_scope
from app.tools.runner import DockerRunner

logger = logging.getLogger(__name__)

OUTPUTS = {
    "TASK_DECOMPOSITION": ("task-plan", "plan", "requirement-analysis", "DERIVED_FROM"),
    "ARCHITECTURE_DESIGN": ("architecture", "architecture", "task-plan", "DERIVED_FROM"),
    "IMPLEMENTATION": (
        "implementation-candidate",
        "implementation_candidate",
        "architecture",
        "IMPLEMENTS",
    ),
    "TEST_DESIGN": ("test-plan", "test_plan", "architecture", "VALIDATES"),
    "DOCUMENTATION_DRAFT": ("documentation", "documentation", "architecture", "DOCUMENTS"),
    "DOCUMENTATION_FINALIZATION": (
        "documentation",
        "documentation",
        "implementation-candidate",
        "DOCUMENTS",
    ),
    "SECURITY_VALIDATION": (
        "security-evidence",
        "security_evidence",
        "implementation-candidate",
        "VALIDATES",
    ),
    "RELEASE_READINESS": (
        "release-manifest",
        "release_manifest",
        "implementation-candidate",
        "VALIDATES",
    ),
}


class WorkflowRuntime:
    def __init__(self, service: WorkflowService, *, settings: Settings | None = None) -> None:
        self.service = service
        self.factory = service.factory
        self.settings = settings or Settings()
        self.orchestrator = WorkflowOrchestrator(self.factory)
        self.persistence = WorkflowPersistenceService(self.factory, service.workspaces)
        self.tasks: dict[uuid.UUID, asyncio.Task] = {}
        self.wakeups: set[uuid.UUID] = set()

    def validate_provider(self, mode: str) -> None:
        if mode == "openai":
            settings = AgentSettings()
            if (
                not settings.openai_model.strip()
                or not settings.openai_api_key.get_secret_value().strip()
            ):
                raise AgentConfigurationError(
                    "OPENAI_MODEL and OPENAI_API_KEY are required for openai mode"
                )

    def schedule(self, workflow_id: uuid.UUID) -> None:
        self.wakeups.add(workflow_id)
        existing = self.tasks.get(workflow_id)
        if existing is None or existing.done():
            self.tasks[workflow_id] = asyncio.create_task(self._drain(workflow_id))

    async def _drain(self, workflow_id: uuid.UUID) -> None:
        while workflow_id in self.wakeups:
            self.wakeups.discard(workflow_id)
            await self.run(workflow_id)

    async def close(self) -> None:
        for task in self.tasks.values():
            task.cancel()
        await asyncio.gather(*self.tasks.values(), return_exceptions=True)

    async def wait(self, workflow_id: uuid.UUID) -> None:
        task = self.tasks.get(workflow_id)
        if task:
            await task

    async def _provider(self, workflow: WorkflowRun, requirement: Artifact):
        if workflow.provider_mode == "openai":
            settings = AgentSettings()
            return OpenAIAgentProvider(
                model=settings.openai_model,
                api_key=settings.openai_api_key.get_secret_value(),
                workspaces=self.service.workspaces,
                policy_engine=PolicyEngine(self.factory),
            )
        fixture = self.service.loader.load(workflow.scenario_type)
        outputs = json.loads(
            (self.service.loader.directory(fixture) / "agent_outputs.json").read_text()
        )
        # Fake outputs are visibly fixture-backed, but retain the submitted input.
        outputs["RequirementAgent"]["normalized_requirement"] = requirement.content["requirement"]
        if requirement.content.get("clarifications"):
            clarified = json.loads(
                (
                    self.service.loader.scenario_root / "greenfield" / "agent_outputs.json"
                ).read_text()
            )
            clarified["RequirementAgent"]["normalized_requirement"] = requirement.content[
                "requirement"
            ]
            clarified["RequirementAgent"]["assumptions"] = [
                f"{item['question']} {item['answer']}"
                for item in requirement.content["clarifications"]
            ]
            outputs = clarified
        return FakeAgentProvider(outputs)

    async def _records(self, workflow_id):
        async with session_scope(self.factory) as session:
            workflow = await session.get(WorkflowRun, workflow_id)
            if workflow is None:
                raise KeyError(workflow_id)
            artifacts = list(
                await session.scalars(
                    select(Artifact)
                    .where(Artifact.workflow_id == workflow_id)
                    .order_by(Artifact.logical_name, Artifact.version.desc())
                )
            )
            current = {}
            for artifact in artifacts:
                current.setdefault(artifact.logical_name, artifact)
            return workflow, current

    async def run(self, workflow_id: uuid.UUID) -> None:
        try:
            workflow, artifacts = await self._records(workflow_id)
            if workflow.status is WorkflowStatus.CREATED:
                await self.orchestrator.transition_workflow(
                    workflow_id,
                    WorkflowStatus.RUNNING,
                    TransitionContext(
                        actor_type="SYSTEM",
                        actor_id="workflow-runtime",
                        expected_version=workflow.version,
                    ),
                )
            graph = await self.service.graph_for(workflow_id)
            scheduler = WorkflowScheduler.configured(
                self.factory,
                graph,
                {stage.executor: self.execute for stage in graph.stages},
                settings=self.settings,
            )
            for _ in range(100):
                workflow, artifacts = await self._records(workflow_id)
                if workflow.status is not WorkflowStatus.RUNNING:
                    return
                # Clarification creates only intake/analysis; initialize its later stages
                # after fresh analysis. Selective requirement replans already own their closure.
                if artifacts["requirement"].content.get("clarifications"):
                    await self._initialize_clarified_stages(workflow, graph)
                view = await self.service.status(workflow_id)
                for checkpoint_name, artifact_name, approval_type in (
                    ("ARCHITECTURE_APPROVAL", "architecture", ApprovalType.ARCHITECTURE),
                    ("RELEASE_APPROVAL", "release-manifest", ApprovalType.RELEASE),
                ):
                    stage = next(s for s in view.stages if s.stage_name == checkpoint_name)
                    if stage.status is StageStatus.READY:
                        artifact = artifacts[artifact_name]
                        checkpoint = await self.orchestrator.request_approval_checkpoint(
                            workflow_id,
                            approval_type=approval_type,
                            artifact_id=artifact.id,
                            artifact_version=artifact.version,
                            context=TransitionContext(
                                actor_type="SYSTEM",
                                actor_id="workflow-runtime",
                                expected_version=workflow.version,
                            ),
                        )
                        if checkpoint.workflow_status is WorkflowStatus.WAITING_FOR_APPROVAL:
                            return
                cycle = await scheduler.run_cycle(workflow_id)
                if not cycle.work:
                    async with session_scope(self.factory) as session:
                        due = await session.scalar(
                            select(StageRun.retry_due_at)
                            .where(
                                StageRun.workflow_id == workflow_id,
                                StageRun.generation == workflow.generation,
                                StageRun._status == StageStatus.RETRY_PENDING,
                                StageRun.retry_due_at.is_not(None),
                            )
                            .order_by(StageRun.retry_due_at)
                            .limit(1)
                        )
                    if due is not None:
                        await asyncio.sleep(
                            max(0.05, min(30, (due - datetime.now(UTC)).total_seconds()))
                        )
                        continue
                    return
                if any(work.stage_name == "COMPLETED" and work.succeeded for work in cycle.work):
                    await self.orchestrator.transition_workflow(
                        workflow_id,
                        WorkflowStatus.COMPLETED,
                        TransitionContext(actor_type="SYSTEM", actor_id="workflow-runtime"),
                        completion_verified=True,
                    )
                    return
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("workflow_runtime_failed", extra={"workflow_id": str(workflow_id)})
            view = await self.service.status(workflow_id)
            if view.status is WorkflowStatus.RUNNING:
                stage = next(
                    (
                        s
                        for s in view.stages
                        if s.status in {StageStatus.READY, StageStatus.RUNNING, StageStatus.FAILED}
                    ),
                    None,
                )
                if stage and stage.stage_run_id:
                    await self.orchestrator.safe_stop(
                        stage.stage_run_id,
                        failure_reason="Workflow runtime could not continue safely",
                        failure_code="INVALID_WORKFLOW_STATE",
                        recommended_action=(
                            "Inspect runtime logs and current artifact evidence before resuming"
                        ),
                        context=TransitionContext(actor_type="SYSTEM", actor_id="workflow-runtime"),
                    )

    async def _initialize_clarified_stages(self, workflow, graph):
        async with session_scope(self.factory) as session:
            names = set(
                await session.scalars(
                    select(StageRun.stage_name).where(
                        StageRun.workflow_id == workflow.id,
                        StageRun.generation == workflow.generation,
                    )
                )
            )
        for stage in graph.stages:
            if stage.name not in names:
                await self.persistence.add_stage_attempt(
                    workflow.id,
                    stage_name=stage.name,
                    generation=workflow.generation,
                    attempt=1,
                    executor=stage.executor,
                )

    @staticmethod
    def _evidence(artifacts, name):
        artifact = artifacts.get(name)
        if artifact is None:
            return None
        return ArtifactEvidence(
            id=artifact.id,
            version=artifact.version,
            sha256=artifact.content_sha256,
            artifact_type=artifact.artifact_type,
            content=artifact.content,
        )

    async def execute(self, claim: StageClaim) -> dict | StageCompletion:
        workflow, artifacts = await self._records(claim.workflow_id)
        requirement = artifacts["requirement"]
        if claim.stage_name == "INTAKE":
            return {
                "requirementArtifactId": str(requirement.id),
                "requirementVersion": requirement.version,
            }
        if claim.stage_name in {"ARCHITECTURE_APPROVAL", "RELEASE_APPROVAL", "COMPLETED"}:
            artifact_name = (
                "architecture"
                if claim.stage_name == "ARCHITECTURE_APPROVAL"
                else "release-manifest"
            )
            approval_type = "ARCHITECTURE" if artifact_name == "architecture" else "RELEASE"
            artifact = artifacts[artifact_name]
            async with session_scope(self.factory) as session:
                approved = await session.scalar(
                    select(Approval.id).where(
                        Approval.workflow_id == claim.workflow_id,
                        Approval.approval_type == approval_type,
                        Approval.status == "APPROVED",
                        Approval.artifact_id == artifact.id,
                        Approval.artifact_version == artifact.version,
                        Approval.artifact_hash == artifact.content_sha256,
                    )
                )
            if approved is None:
                raise InvalidWorkflowStateFailure("Exact artifact version has no human approval")
            return {"approvalId": str(approved), "artifactId": str(artifact.id)}
        if claim.stage_name in {"BUILD_VALIDATION", "UNIT_TEST", "INTEGRATION_TEST"}:
            with self.service.workspaces.for_workflow(claim.workflow_id) as workspace:
                receipt = await DockerRunner().run(
                    workspace,
                    "mvn package" if claim.stage_name == "BUILD_VALIDATION" else "mvn test",
                    build=claim.stage_name == "BUILD_VALIDATION",
                )
            ref = await self.persistence.store_artifact(
                claim.workflow_id,
                ArtifactInput(
                    logical_name=claim.stage_name.lower() + "-evidence",
                    artifact_type="validation_evidence",
                    schema_version="1",
                    producer_stage_run_id=claim.stage_run_id,
                    content=receipt.as_dict(),
                ),
            )
            if receipt.exit_code != 0 or receipt.error:
                raise FailedTestAssertion(
                    "Candidate validation did not succeed; inspect the runner receipt"
                )
            return {"artifactId": str(ref.id), "exitCode": receipt.exit_code}
        specialist = SPECIALISTS.get(claim.executor)
        if specialist is None:
            raise InvalidWorkflowStateFailure(f"No specialist binding for {claim.executor}")
        if claim.stage_name == "ARCHITECTURE_DESIGN":
            verdict = ArchitectureEntryGate().evaluate(
                GateContext(
                    requirement=self._evidence(artifacts, "requirement-analysis"),
                    task_plan=self._evidence(artifacts, "task-plan"),
                )
            )
            if verdict.result is not GateResult.PASS:
                raise InvalidWorkflowStateFailure("; ".join(verdict.reasons))
        if claim.stage_name in {"IMPLEMENTATION", "TEST_DESIGN", "DOCUMENTATION_DRAFT"}:
            async with session_scope(self.factory) as session:
                approvals = tuple(
                    ApprovalEvidence(
                        id=a.id,
                        approval_type=a.approval_type,
                        status=ApprovalStatus(a.status),
                        artifact_id=a.artifact_id,
                        artifact_version=a.artifact_version,
                        artifact_hash=a.artifact_hash,
                    )
                    for a in await session.scalars(
                        select(Approval).where(Approval.workflow_id == claim.workflow_id)
                    )
                )
            verdict = ImplementationEntryGate().evaluate(
                GateContext(
                    architecture=self._evidence(artifacts, "architecture"),
                    approvals=approvals,
                )
            )
            if verdict.result is not GateResult.PASS:
                raise InvalidWorkflowStateFailure("; ".join(verdict.reasons))
        if claim.stage_name == "RELEASE_READINESS":
            view = await self.service.status(claim.workflow_id)
            verdict = ReleaseReadinessEntryGate().evaluate(
                GateContext(
                    stages=tuple(
                        StageEvidence(
                            stage_name=s.stage_name, status=s.status, generation=s.generation
                        )
                        for s in view.stages
                    )
                )
            )
            if verdict.result is not GateResult.PASS:
                raise InvalidWorkflowStateFailure("; ".join(verdict.reasons))
        files = ()
        with self.service.workspaces.for_workflow(claim.workflow_id) as workspace:
            files = tuple(
                FileSnapshot(name=name, version=1, content=workspace.read_file(name))
                for name in workspace.list_files()[:128]
                if name.endswith((".java", ".sql", ".md", ".yml", ".yaml"))
            )
        context = AgentContext(
            workflow_id=claim.workflow_id,
            stage_run_id=claim.stage_run_id,
            generation=claim.generation,
            attempt=claim.attempt,
            trace_id=uuid.uuid4(),
            requirement=requirement.content["requirement"],
            artifacts=tuple(
                Snapshot(name=a.logical_name, version=a.version, content=json.dumps(a.content))
                for a in artifacts.values()
                if a.artifact_type != "workflow_graph"
            ),
            files=files,
            authorized_tools=specialist.allowed_tools,
        )
        result = await (await self._provider(workflow, requirement)).run(specialist, context)
        content = result.output.model_dump(mode="json")
        if claim.stage_name == "REQUIREMENT_ANALYSIS":
            verdict = RequirementExitGate().evaluate(
                GateContext(
                    requirement=ArtifactEvidence(
                        id=uuid.uuid4(),
                        version=1,
                        sha256=canonical_content(content)[1],
                        artifact_type="requirement_analysis",
                        content=content,
                    )
                )
            )
            if verdict.result is not GateResult.PASS:
                raise InvalidWorkflowStateFailure("; ".join(verdict.reasons))
            await self.orchestrator.record_requirement_analysis(
                claim.workflow_id,
                requirement_artifact_id=requirement.id,
                result=result,
                context=TransitionContext(
                    actor_type="SYSTEM", actor_id="workflow-runtime", trace_id=context.trace_id
                ),
                claim=claim,
            )
            return StageCompletion(claim.stage_run_id, claim.stage_name, True, 0)
        logical_name, artifact_type, parent_name, relationship = OUTPUTS[claim.stage_name]
        if claim.stage_name == "ARCHITECTURE_DESIGN":
            verdict = ArchitectureExitGate().evaluate(
                GateContext(
                    architecture=ArtifactEvidence(
                        id=uuid.uuid4(),
                        version=1,
                        sha256=canonical_content(content)[1],
                        artifact_type="architecture",
                        content=content,
                    )
                )
            )
            if verdict.result is not GateResult.PASS:
                raise InvalidWorkflowStateFailure("; ".join(verdict.reasons))
        ref = await self.persistence.store_artifact(
            claim.workflow_id,
            ArtifactInput(
                logical_name=logical_name,
                artifact_type=artifact_type,
                schema_version=result.schema_version,
                content=content,
                producer_stage_run_id=claim.stage_run_id,
                requirement_ids=["REQ-WORKFLOW"],
                component_ids=["URL-SHORTENER"],
            ),
        )
        parent = artifacts[parent_name]
        await self.persistence.link_artifacts(
            claim.workflow_id,
            parent_artifact_id=parent.id,
            child_artifact_id=ref.id,
            relationship=relationship,
        )
        if claim.stage_name == "SECURITY_VALIDATION" and content.get("blocking"):
            raise SecurityViolationFailure("Security specialist reported blocking findings")
        return {
            "artifactId": str(ref.id),
            "artifactVersion": ref.version,
            "provider": result.provider,
            "contextSha256": result.context_sha256,
        }
