"""Prepare immutable scenario seeds in workflow-owned workspaces."""

import hashlib
import json
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.orchestration.contracts import ScenarioType
from app.scenarios.fixtures import ScenarioFixture, ScenarioFixtureLoader
from app.scenarios.impact import ImpactAnalysis, SourceImpactAnalyzer
from app.tools.workspaces import WorkspaceManager


@dataclass(frozen=True)
class PreparedScenario:
    fixture: ScenarioFixture
    workflow_id: uuid.UUID
    workspace_path: Path
    seed_sha256: str
    files: tuple[str, ...]
    impact: ImpactAnalysis | None


class ScenarioFixtureRunner:
    _IGNORED_PARTS = frozenset({".git", ".idea", ".pytest_cache", "__pycache__", "build", "target"})

    def __init__(
        self,
        *,
        loader: ScenarioFixtureLoader | None = None,
        workspaces: WorkspaceManager | None = None,
        impact_analyzer: SourceImpactAnalyzer | None = None,
    ) -> None:
        self.loader = loader or ScenarioFixtureLoader()
        self.workspaces = workspaces or WorkspaceManager()
        self.impact_analyzer = impact_analyzer or SourceImpactAnalyzer()

    def prepare(self, scenario: ScenarioType | str, workflow_id: uuid.UUID) -> PreparedScenario:
        fixture = self.loader.load(scenario)
        seed = self.loader.seed_directory(fixture)
        with self.workspaces.for_workflow(workflow_id) as workspace:
            if workspace.list_files():
                raise ValueError("Scenario workspace must be empty before seed materialization")
            for source in sorted(
                path
                for path in seed.rglob("*")
                if path.is_file()
                and not self._IGNORED_PARTS.intersection(path.relative_to(seed).parts)
            ):
                relative = source.relative_to(seed).as_posix()
                if relative == ".gitkeep":
                    continue
                workspace.write_file(relative, source.read_text(encoding="utf-8"))
            files = tuple(workspace.list_files())
            seed_sha256 = self._workspace_hash(workspace, files)
            impact = (
                self.impact_analyzer.analyze(workspace)
                if fixture.scenario is ScenarioType.BROWNFIELD
                else None
            )
            return PreparedScenario(
                fixture=fixture,
                workflow_id=workflow_id,
                workspace_path=workspace.path,
                seed_sha256=seed_sha256,
                files=files,
                impact=impact,
            )

    @staticmethod
    def _workspace_hash(workspace, files: tuple[str, ...]) -> str:
        entries = [
            {"path": path, "sha256": hashlib.sha256(workspace.read_bytes(path)).hexdigest()}
            for path in files
        ]
        return hashlib.sha256(
            json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
