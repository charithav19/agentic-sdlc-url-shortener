"""Named end-to-end tests required by the scenario acceptance contract."""

import json
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.contracts import AgentContext, Snapshot
from app.agents.fake_provider import FakeAgentProvider
from app.artifacts.schemas import ArtifactInput
from app.governance.approvals import ApprovalStatus
from app.orchestration.clarifications import RequirementAnalysisRunner
from app.orchestration.commands import TransitionContext
from app.orchestration.contracts import ScenarioType, StageStatus, WorkflowStatus
from app.orchestration.orchestrator import WorkflowOrchestrator
from app.persistence.models import Approval, Artifact, StageRun, WorkflowRun
from app.persistence.service import WorkflowPersistenceService
from app.persistence.unit_of_work import UnitOfWork
from app.scenarios.evidence import ScenarioPreparationEvidence
from app.scenarios.fixtures import ScenarioFixtureLoader
from app.scenarios.runner import ScenarioFixtureRunner
from app.tools.workspaces import WorkspaceManager
from tests.scenarios.harness import CompleteScenarioHarness

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _overlapped(intervals: dict[str, tuple[float, float]], expected: set[str]) -> bool:
    selected = [intervals[name] for name in expected]
    return max(start for start, _ in selected) < min(end for _, end in selected)


@pytest.mark.integration
@pytest.mark.asyncio
class GreenfieldScenarioIT:
    async def test_complete_requirement_to_release_path(
        self,
        phase6_factory: async_sessionmaker[AsyncSession],
        tmp_path: Path,
    ) -> None:
        result = await CompleteScenarioHarness(
            phase6_factory,
            repository_root=REPOSITORY_ROOT,
            workspace_root=tmp_path / "workspaces",
        ).run(ScenarioType.GREENFIELD)

        assert result.prepared.fixture.requirement == (
            "Build URL shortener with core APIs, analytics and reliability."
        )
        assert not any(
            segment in path
            for path in result.prepared.files
            for segment in ("/api/", "/application/", "/domain/", "/persistence/")
        )
        preparation = ScenarioPreparationEvidence.from_prepared(result.prepared)
        assert preparation.scenario == "GREENFIELD"
        assert preparation.seed_sha256 == result.prepared.seed_sha256
        assert {
            "requirement",
            "requirement-analysis",
            "task-plan",
            "architecture",
            "implementation-candidate",
            "test-plan",
            "documentation",
            "documentation-final",
            "build-evidence",
            "unit-test-evidence",
            "integration-test-evidence",
            "security-evidence",
            "release-manifest",
        } <= set(result.artifacts)
        assert _overlapped(
            result.parallel_intervals,
            {"IMPLEMENTATION", "TEST_DESIGN", "DOCUMENTATION_DRAFT"},
        )
        assert _overlapped(
            result.parallel_intervals,
            {"UNIT_TEST", "INTEGRATION_TEST", "SECURITY_VALIDATION"},
        )

        async with UnitOfWork.open(phase6_factory) as unit:
            workflow = await unit.session.get(WorkflowRun, result.workflow_id)
            stages = list(
                await unit.session.scalars(
                    select(StageRun).where(StageRun.workflow_id == result.workflow_id)
                )
            )
            approvals = list(
                await unit.session.scalars(
                    select(Approval).where(Approval.workflow_id == result.workflow_id)
                )
            )
            events = await unit.audit.page(result.workflow_id, limit=500)
        assert workflow is not None and workflow.status is WorkflowStatus.COMPLETED
        assert len(stages) == 16
        assert {stage.status for stage in stages} == {StageStatus.SUCCEEDED}
        assert {approval.status for approval in approvals} == {ApprovalStatus.APPROVED.value}
        assert [approval.approval_type for approval in approvals] == [
            "ARCHITECTURE",
            "RELEASE",
        ]
        assert sum(event.event_type == "WORKFLOW_STATUS_CHANGED" for event in events) >= 6
        assert any(event.event_type == "APPROVAL_REQUESTED" for event in events)
        assert any(event.event_type == "STAGE_CLAIM_COMPLETED" for event in events)


@pytest.mark.integration
@pytest.mark.asyncio
class BrownfieldScenarioIT:
    async def test_source_driven_impact_and_complete_release_path(
        self,
        phase6_factory: async_sessionmaker[AsyncSession],
        tmp_path: Path,
    ) -> None:
        result = await CompleteScenarioHarness(
            phase6_factory,
            repository_root=REPOSITORY_ROOT,
            workspace_root=tmp_path / "workspaces",
        ).run(ScenarioType.BROWNFIELD)
        impact = result.prepared.impact
        assert impact is not None
        assert set(impact.responsibilities) == set(
            result.prepared.fixture.expected_affected_responsibilities
        )
        assert all(
            path in impact.inspected_files
            for paths in impact.affected_files.values()
            for path in paths
        )
        assert any(
            path.endswith("LinkController.java") for path in impact.affected_files["controller"]
        )
        assert any(
            path.endswith("RedirectController.java")
            for path in impact.affected_files["redirect_behavior"]
        )
        assert any(path.endswith("Link.java") for path in impact.affected_files["domain_entity"])
        assert any(
            path.endswith("LinkRepository.java") for path in impact.affected_files["repository"]
        )
        assert any(
            path.endswith("V1__create_links.sql") for path in impact.affected_files["migration"]
        )
        assert any(
            path.endswith("CoreRegressionTest.java") for path in impact.affected_files["tests"]
        )
        assert impact.affected_files["openapi_docs"]

        async with UnitOfWork.open(phase6_factory) as unit:
            workflow = await unit.session.get(WorkflowRun, result.workflow_id)
            source_impact = await unit.session.scalar(
                select(Artifact).where(
                    Artifact.workflow_id == result.workflow_id,
                    Artifact.logical_name == "source-impact",
                )
            )
            plan = await unit.session.scalar(
                select(Artifact).where(
                    Artifact.workflow_id == result.workflow_id,
                    Artifact.logical_name == "task-plan",
                )
            )
            implementation = await unit.session.scalar(
                select(Artifact).where(
                    Artifact.workflow_id == result.workflow_id,
                    Artifact.logical_name == "implementation-candidate",
                )
            )
        assert workflow is not None and workflow.status is WorkflowStatus.COMPLETED
        assert source_impact is not None
        assert set(source_impact.content["affectedFiles"]) == set(impact.responsibilities)
        assert plan is not None
        assert set(plan.content["affected_components"]) == set(impact.responsibilities)
        assert implementation is not None
        changed = set(implementation.content["changed_files"])
        discovered = {path for paths in impact.affected_files.values() for path in paths}
        assert changed <= discovered

    async def test_impact_discovery_uses_source_markers_after_renaming(
        self, tmp_path: Path
    ) -> None:
        workspaces = WorkspaceManager(tmp_path / "workspaces")
        runner = ScenarioFixtureRunner(
            loader=ScenarioFixtureLoader(REPOSITORY_ROOT), workspaces=workspaces
        )
        workflow_id = uuid.uuid4()
        prepared = runner.prepare(ScenarioType.BROWNFIELD, workflow_id)
        original = "src/main/java/com/schwab/urlshortener/application/LinkService.java"
        renamed = "src/main/java/example/RenamedApplicationComponent.java"
        with workspaces.for_workflow(workflow_id) as workspace:
            content = workspace.read_file(original).replace("LinkService", "RenamedComponent")
            workspace.write_file(renamed, content)
            analysis = runner.impact_analyzer.analyze(workspace)
        assert renamed in analysis.affected_files["service"]
        assert (
            "RenamedApplicationComponent" not in prepared.fixture.expected_affected_responsibilities
        )


@pytest.mark.integration
@pytest.mark.asyncio
class AmbiguousScenarioIT:
    async def test_pauses_for_clarification_before_any_implementation(
        self,
        phase6_factory: async_sessionmaker[AsyncSession],
        tmp_path: Path,
    ) -> None:
        workspaces = WorkspaceManager(tmp_path / "workspaces")
        persistence = WorkflowPersistenceService(phase6_factory, workspaces)
        orchestrator = WorkflowOrchestrator(phase6_factory)
        workflow_id = await persistence.create_workflow(
            scenario_type=ScenarioType.AMBIGUOUS,
            provider_mode="fake",
            workspace_ref="ambiguous-fixture",
        )
        prepared = ScenarioFixtureRunner(
            loader=ScenarioFixtureLoader(REPOSITORY_ROOT), workspaces=workspaces
        ).prepare(ScenarioType.AMBIGUOUS, workflow_id)
        outputs = json.loads(
            (REPOSITORY_ROOT / "apps/orchestrator/tests/fixtures/ambiguous.json").read_text()
        )
        await orchestrator.transition_workflow(
            workflow_id,
            WorkflowStatus.RUNNING,
            TransitionContext(actor_type="SYSTEM", actor_id="ambiguous-scenario"),
        )
        requirement = await persistence.store_artifact(
            workflow_id,
            ArtifactInput(
                logical_name="requirement",
                artifact_type="requirement",
                schema_version="1",
                content={"requirement": prepared.fixture.requirement},
                requirement_ids=["REQ-SAFETY"],
                component_ids=["URL-SHORTENER"],
            ),
        )
        analysis_stage = await persistence.add_stage_attempt(
            workflow_id,
            stage_name="REQUIREMENT_ANALYSIS",
            generation=1,
            attempt=1,
            executor="requirements_specialist",
            input_artifacts=[requirement],
        )
        implementation_stage = await persistence.add_stage_attempt(
            workflow_id,
            stage_name="IMPLEMENTATION",
            generation=1,
            attempt=1,
            executor="implementation_specialist",
        )
        await orchestrator.transition_stage(
            analysis_stage,
            StageStatus.READY,
            TransitionContext(actor_type="SYSTEM", actor_id="ambiguous-scenario"),
        )
        await orchestrator.transition_stage(
            implementation_stage,
            StageStatus.BLOCKED,
            TransitionContext(actor_type="SYSTEM", actor_id="ambiguous-scenario"),
        )
        analysis = await RequirementAnalysisRunner(orchestrator, FakeAgentProvider(outputs)).run(
            requirement_artifact_id=requirement.id,
            agent_context=AgentContext(
                workflow_id=workflow_id,
                stage_run_id=analysis_stage,
                trace_id=uuid.uuid4(),
                generation=1,
                attempt=1,
                requirement=prepared.fixture.requirement,
                artifacts=(
                    Snapshot(name="requirement", version=1, content=prepared.fixture.requirement),
                ),
            ),
            transition_context=TransitionContext(
                actor_type="SYSTEM", actor_id="requirement-runner"
            ),
        )
        assert analysis.workflow_status is WorkflowStatus.WAITING_FOR_CLARIFICATION
        assert set(analysis.questions) == set(
            json.loads((REPOSITORY_ROOT / "scenarios/ambiguous/answers.json").read_text())
        )

        async with UnitOfWork.open(phase6_factory) as unit:
            workflow = await unit.session.get(WorkflowRun, workflow_id)
            implementation = await unit.session.get(StageRun, implementation_stage)
            implementation_events = list(
                await unit.session.scalars(
                    select(StageRun).where(
                        StageRun.workflow_id == workflow_id,
                        StageRun.stage_name == "IMPLEMENTATION",
                    )
                )
            )
        assert workflow is not None
        assert workflow.status is WorkflowStatus.WAITING_FOR_CLARIFICATION
        assert implementation is not None and implementation.status is StageStatus.BLOCKED
        assert all(stage.started_at is None for stage in implementation_events)
