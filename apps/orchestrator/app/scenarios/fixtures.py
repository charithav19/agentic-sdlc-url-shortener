"""Strict loading for repository-owned scenario fixtures."""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.orchestration.contracts import ScenarioType


class ScenarioFixture(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scenario: ScenarioType
    requirement: str = Field(min_length=1)
    seed: str = "seed"
    provider_mode: str = "fake"
    expected_checkpoints: tuple[str, ...]
    expected_artifacts: tuple[str, ...]
    expected_affected_responsibilities: tuple[str, ...] = ()

    @field_validator("seed")
    @classmethod
    def relative_seed(cls, value: str) -> str:
        path = Path(value)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("Scenario seed must be relative to its fixture directory")
        return value


class ScenarioFixtureLoader:
    def __init__(self, repository_root: Path | None = None) -> None:
        self.repository_root = repository_root or Path(__file__).resolve().parents[4]
        self.scenario_root = self.repository_root / "scenarios"
        if not self.scenario_root.is_dir() and repository_root is None:
            self.scenario_root = Path(__file__).resolve().parents[1] / "resources" / "scenarios"

    def load(self, scenario: ScenarioType | str) -> ScenarioFixture:
        scenario_type = scenario if isinstance(scenario, ScenarioType) else ScenarioType(scenario)
        directory = self.scenario_root / scenario_type.value.lower()
        payload = yaml.safe_load((directory / "scenario.yaml").read_text(encoding="utf-8"))
        requirement_path = directory / payload.pop("requirement_file")
        payload["requirement"] = requirement_path.read_text(encoding="utf-8").strip()
        fixture = ScenarioFixture.model_validate(payload)
        if fixture.scenario is not scenario_type:
            raise ValueError("Scenario fixture identity does not match its directory")
        return fixture

    def directory(self, fixture: ScenarioFixture) -> Path:
        return self.scenario_root / fixture.scenario.value.lower()

    def seed_directory(self, fixture: ScenarioFixture) -> Path:
        seed = (self.directory(fixture) / fixture.seed).resolve()
        directory = self.directory(fixture).resolve()
        if not seed.is_relative_to(directory) or not seed.is_dir():
            raise ValueError("Scenario seed is missing or outside its fixture directory")
        return seed
