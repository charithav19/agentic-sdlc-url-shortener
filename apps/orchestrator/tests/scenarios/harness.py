"""Deterministic full-DAG harness using only production orchestration services."""

import asyncio
import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.architecture import ArchitectureAgent
from app.agents.contracts import AgentContext, FileSnapshot, Snapshot, Specialist
from app.agents.documentation import DocumentationAgent
from app.agents.fake_provider import FakeAgentProvider
from app.agents.implementation import ImplementationAgent
from app.agents.planning import PlanningAgent
from app.agents.release_readiness import ReleaseReadinessAgent
from app.agents.requirement import RequirementAgent
from app.agents.security import SecurityAgent
from app.agents.testing import TestAgent
from app.artifacts.lineage import LineageRelationship
from app.artifacts.schemas import ArtifactInput, ArtifactRef
from app.governance.approvals import ApprovalDecision, ApprovalType
from app.orchestration.claims import StageClaim
from app.orchestration.commands import TransitionContext
from app.orchestration.contracts import ScenarioType, WorkflowStatus
from app.orchestration.graph_loader import load_graph
from app.orchestration.orchestrator import WorkflowOrchestrator
from app.orchestration.scheduler import WorkflowScheduler
from app.persistence.service import WorkflowPersistenceService
from app.scenarios.fixtures import ScenarioFixtureLoader
from app.scenarios.runner import PreparedScenario, ScenarioFixtureRunner
from app.tools.workspaces import WorkspaceManager


@dataclass(frozen=True)
class CompleteScenarioResult:
    workflow_id: uuid.UUID
    prepared: PreparedScenario
    artifacts: dict[str, ArtifactRef]
    parallel_intervals: dict[str, tuple[float, float]]
    architecture_approval_id: uuid.UUID
    release_approval_id: uuid.UUID


class CompleteScenarioHarness:
    _SPECIALISTS: dict[str, Specialist] = {
        "REQUIREMENT_ANALYSIS": RequirementAgent(),
        "TASK_DECOMPOSITION": PlanningAgent(),
        "ARCHITECTURE_DESIGN": ArchitectureAgent(),
        "IMPLEMENTATION": ImplementationAgent(),
        "TEST_DESIGN": TestAgent(),
        "DOCUMENTATION_DRAFT": DocumentationAgent(),
        "DOCUMENTATION_FINALIZATION": DocumentationAgent(),
        "SECURITY_VALIDATION": SecurityAgent(),
        "RELEASE_READINESS": ReleaseReadinessAgent(),
    }
    _ARTIFACTS = {
        "REQUIREMENT_ANALYSIS": ("requirement-analysis", "requirement_analysis"),
        "TASK_DECOMPOSITION": ("task-plan", "plan"),
        "ARCHITECTURE_DESIGN": ("architecture", "architecture"),
        "IMPLEMENTATION": ("implementation-candidate", "implementation_candidate"),
        "TEST_DESIGN": ("test-plan", "test_plan"),
        "DOCUMENTATION_DRAFT": ("documentation", "documentation"),
        "BUILD_VALIDATION": ("build-evidence", "validation_evidence"),
        "UNIT_TEST": ("unit-test-evidence", "validation_evidence"),
        "INTEGRATION_TEST": ("integration-test-evidence", "validation_evidence"),
        "SECURITY_VALIDATION": ("security-evidence", "security_evidence"),
        "DOCUMENTATION_FINALIZATION": ("documentation", "documentation"),
        "RELEASE_READINESS": ("release-manifest", "release_manifest"),
    }

    def __init__(
        self,
        factory: async_sessionmaker[AsyncSession],
        *,
        repository_root: Path,
        workspace_root: Path,
    ) -> None:
        self.factory = factory
        self.workspaces = WorkspaceManager(workspace_root)
        self.fixture_runner = ScenarioFixtureRunner(
            loader=ScenarioFixtureLoader(repository_root),
            workspaces=self.workspaces,
        )
        self.persistence = WorkflowPersistenceService(factory, self.workspaces)
        self.orchestrator = WorkflowOrchestrator(factory)

    async def run(self, scenario: ScenarioType) -> CompleteScenarioResult:
        workflow_id = await self.persistence.create_workflow(
            scenario_type=scenario,
            provider_mode="fake",
            workspace_ref=f"{scenario.value.lower()}-fixture",
        )
        prepared = self.fixture_runner.prepare(scenario, workflow_id)
        fixture_path = (
            Path(__file__).resolve().parents[1] / "fixtures" / f"{scenario.value.lower()}.json"
        )
        provider = FakeAgentProvider(json.loads(fixture_path.read_text(encoding="utf-8")))
        graph = load_graph()
        for stage in graph.stages:
            await self.persistence.add_stage_attempt(
                workflow_id,
                stage_name=stage.name,
                generation=1,
                attempt=1,
                executor=stage.executor,
            )
        requirement = await self.persistence.store_artifact(
            workflow_id,
            ArtifactInput(
                logical_name="requirement",
                artifact_type="requirement",
                schema_version="1",
                content={"requirement": prepared.fixture.requirement},
                requirement_ids=["REQ-SCENARIO"],
                component_ids=["URL-SHORTENER"],
            ),
        )
        artifacts: dict[str, ArtifactRef] = {"requirement": requirement}
        if prepared.impact is not None:
            artifacts["source-impact"] = await self.persistence.store_artifact(
                workflow_id,
                ArtifactInput(
                    logical_name="source-impact",
                    artifact_type="source_impact",
                    schema_version="1",
                    content={
                        "inspectedFiles": list(prepared.impact.inspected_files),
                        "affectedFiles": {
                            key: list(value)
                            for key, value in prepared.impact.affected_files.items()
                        },
                    },
                    requirement_ids=["REQ-SCENARIO"],
                    component_ids=list(prepared.impact.responsibilities),
                ),
            )
            await self.persistence.link_artifacts(
                workflow_id,
                parent_artifact_id=requirement.id,
                child_artifact_id=artifacts["source-impact"].id,
                relationship=LineageRelationship.DERIVED_FROM,
                requirement_ids=["REQ-SCENARIO"],
                component_ids=list(prepared.impact.responsibilities),
            )

        await self.orchestrator.transition_workflow(
            workflow_id,
            WorkflowStatus.RUNNING,
            TransitionContext(actor_type="SYSTEM", actor_id="scenario-runner"),
        )
        parallel_intervals: dict[str, tuple[float, float]] = {}
        artifact_lock = asyncio.Lock()
        groups = {
            "engineering": {
                "IMPLEMENTATION",
                "TEST_DESIGN",
                "DOCUMENTATION_DRAFT",
            },
            "validation": {"UNIT_TEST", "INTEGRATION_TEST", "SECURITY_VALIDATION"},
        }
        started = {name: set() for name in groups}
        barriers = {name: asyncio.Event() for name in groups}
        files = self._file_snapshots(prepared)

        async def executor(claim: StageClaim) -> dict:
            group_name = next(
                (name for name, members in groups.items() if claim.stage_name in members), None
            )
            start = time.monotonic()
            if group_name is not None:
                started[group_name].add(claim.stage_name)
                if started[group_name] == groups[group_name]:
                    barriers[group_name].set()
                await asyncio.wait_for(barriers[group_name].wait(), timeout=2)

            content: dict = {
                "stage": claim.stage_name,
                "status": "PASSED",
                "seedSha256": prepared.seed_sha256,
            }
            specialist = self._SPECIALISTS.get(claim.stage_name)
            if specialist is not None:
                result = await provider.run(
                    specialist,
                    AgentContext(
                        workflow_id=workflow_id,
                        stage_run_id=claim.stage_run_id,
                        trace_id=uuid.uuid4(),
                        generation=claim.generation,
                        attempt=claim.attempt,
                        requirement=prepared.fixture.requirement,
                        artifacts=(
                            Snapshot(
                                name="requirement",
                                version=1,
                                content=prepared.fixture.requirement,
                            ),
                        ),
                        files=files,
                    ),
                )
                content = result.output.model_dump(mode="json")
                content["provider"] = result.provider
                content["contextSha256"] = result.context_sha256
            artifact_spec = self._ARTIFACTS.get(claim.stage_name)
            if artifact_spec is not None:
                logical_name, artifact_type = artifact_spec
                async with artifact_lock:
                    ref = await self.persistence.store_artifact(
                        workflow_id,
                        ArtifactInput(
                            logical_name=logical_name,
                            artifact_type=artifact_type,
                            schema_version="1",
                            content=content,
                            producer_stage_run_id=claim.stage_run_id,
                            requirement_ids=["REQ-SCENARIO"],
                            component_ids=["URL-SHORTENER"],
                        ),
                    )
                    key = (
                        "documentation-final"
                        if claim.stage_name == "DOCUMENTATION_FINALIZATION"
                        else logical_name
                    )
                    artifacts[key] = ref
                    await self._link_output(workflow_id, claim.stage_name, ref, artifacts)
            end = time.monotonic()
            if group_name is not None:
                parallel_intervals[claim.stage_name] = (start, end)
            return content

        executors = {stage.executor: executor for stage in graph.stages}
        scheduler = WorkflowScheduler(
            self.factory,
            graph,
            executors,
            max_parallel_stages=3,
            scheduler_id=f"scenario-{scenario.value.lower()}",
        )

        for expected in (
            "INTAKE",
            "REQUIREMENT_ANALYSIS",
            "TASK_DECOMPOSITION",
            "ARCHITECTURE_DESIGN",
        ):
            await self._cycle(scheduler, workflow_id, {expected})

        architecture = artifacts["architecture"]
        checkpoint = await self.orchestrator.request_approval_checkpoint(
            workflow_id,
            approval_type=ApprovalType.ARCHITECTURE,
            artifact_id=architecture.id,
            artifact_version=architecture.version,
            context=TransitionContext(
                actor_type="SYSTEM", actor_id="scenario-runner", expected_version=2
            ),
        )
        paused = await scheduler.run_cycle(workflow_id)
        if paused.work:
            raise AssertionError("Architecture checkpoint did not pause execution")
        await self.orchestrator.decide_approval(
            workflow_id,
            approval_id=checkpoint.approval_id,
            artifact_id=architecture.id,
            artifact_version=architecture.version,
            decision=ApprovalDecision.APPROVED,
            reviewer_id="scenario-architecture-reviewer",
            reason="Scenario architecture approved for deterministic execution",
            context=TransitionContext(
                actor_type="HUMAN",
                actor_id="scenario-architecture-reviewer",
                expected_version=3,
            ),
        )
        await self._cycle(scheduler, workflow_id, {"ARCHITECTURE_APPROVAL"})
        await self._cycle(scheduler, workflow_id, groups["engineering"])
        await self._cycle(scheduler, workflow_id, {"BUILD_VALIDATION"})
        await self._cycle(scheduler, workflow_id, groups["validation"])
        await self._cycle(scheduler, workflow_id, {"DOCUMENTATION_FINALIZATION"})
        await self._cycle(scheduler, workflow_id, {"RELEASE_READINESS"})

        release = artifacts["release-manifest"]
        release_checkpoint = await self.orchestrator.request_approval_checkpoint(
            workflow_id,
            approval_type=ApprovalType.RELEASE,
            artifact_id=release.id,
            artifact_version=release.version,
            context=TransitionContext(
                actor_type="SYSTEM", actor_id="scenario-runner", expected_version=4
            ),
        )
        paused = await scheduler.run_cycle(workflow_id)
        if paused.work:
            raise AssertionError("Release checkpoint did not pause execution")
        await self.orchestrator.decide_approval(
            workflow_id,
            approval_id=release_checkpoint.approval_id,
            artifact_id=release.id,
            artifact_version=release.version,
            decision=ApprovalDecision.APPROVED,
            reviewer_id="scenario-release-reviewer",
            reason="Scenario release evidence approved",
            context=TransitionContext(
                actor_type="HUMAN",
                actor_id="scenario-release-reviewer",
                expected_version=5,
            ),
        )
        await self._cycle(scheduler, workflow_id, {"RELEASE_APPROVAL"})
        await self._cycle(scheduler, workflow_id, {"COMPLETED"})
        await self.orchestrator.transition_workflow(
            workflow_id,
            WorkflowStatus.COMPLETED,
            TransitionContext(actor_type="SYSTEM", actor_id="scenario-runner", expected_version=6),
            completion_verified=True,
        )
        return CompleteScenarioResult(
            workflow_id=workflow_id,
            prepared=prepared,
            artifacts=artifacts,
            parallel_intervals=parallel_intervals,
            architecture_approval_id=checkpoint.approval_id,
            release_approval_id=release_checkpoint.approval_id,
        )

    @staticmethod
    async def _cycle(
        scheduler: WorkflowScheduler, workflow_id: uuid.UUID, expected: set[str]
    ) -> None:
        cycle = await scheduler.run_cycle(workflow_id)
        actual = {item.stage_name for item in cycle.work if item.succeeded}
        if actual != expected:
            failures = {
                item.stage_name: item.error for item in cycle.work if item.succeeded is False
            }
            raise AssertionError(
                f"Expected stages {sorted(expected)}, executed {sorted(actual)}; "
                f"failures={failures}"
            )

    def _file_snapshots(self, prepared: PreparedScenario) -> tuple[FileSnapshot, ...]:
        if prepared.fixture.scenario is not ScenarioType.BROWNFIELD:
            return ()
        with self.workspaces.for_workflow(prepared.workflow_id) as workspace:
            return tuple(
                FileSnapshot(name=path, version=1, content=workspace.read_file(path))
                for path in prepared.files
                if path.endswith((".java", ".sql", ".yml", ".yaml", ".md"))
            )

    async def _link_output(
        self,
        workflow_id: uuid.UUID,
        stage_name: str,
        output: ArtifactRef,
        artifacts: dict[str, ArtifactRef],
    ) -> None:
        relationships = {
            "REQUIREMENT_ANALYSIS": ("requirement", LineageRelationship.DERIVED_FROM),
            "TASK_DECOMPOSITION": ("requirement-analysis", LineageRelationship.DERIVED_FROM),
            "ARCHITECTURE_DESIGN": ("task-plan", LineageRelationship.DERIVED_FROM),
            "IMPLEMENTATION": ("architecture", LineageRelationship.IMPLEMENTS),
            "TEST_DESIGN": ("architecture", LineageRelationship.VALIDATES),
            "DOCUMENTATION_DRAFT": ("architecture", LineageRelationship.DOCUMENTS),
            "BUILD_VALIDATION": ("implementation-candidate", LineageRelationship.VALIDATES),
            "UNIT_TEST": ("implementation-candidate", LineageRelationship.VALIDATES),
            "INTEGRATION_TEST": ("implementation-candidate", LineageRelationship.VALIDATES),
            "SECURITY_VALIDATION": ("implementation-candidate", LineageRelationship.VALIDATES),
            "DOCUMENTATION_FINALIZATION": (
                "implementation-candidate",
                LineageRelationship.DOCUMENTS,
            ),
            "RELEASE_READINESS": ("implementation-candidate", LineageRelationship.VALIDATES),
        }
        relationship = relationships.get(stage_name)
        if relationship is None:
            return
        parent_name, relationship_type = relationship
        parent = artifacts[parent_name]
        await self.persistence.link_artifacts(
            workflow_id,
            parent_artifact_id=parent.id,
            child_artifact_id=output.id,
            relationship=relationship_type,
            requirement_ids=["REQ-SCENARIO"],
            component_ids=["URL-SHORTENER"],
        )
