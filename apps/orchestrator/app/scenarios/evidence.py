"""Sanitized, serializable evidence for one prepared scenario fixture."""

import hashlib

from pydantic import BaseModel, ConfigDict

from app.scenarios.runner import PreparedScenario


class ScenarioPreparationEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scenario: str
    provider_mode: str
    requirement_sha256: str
    seed_sha256: str
    files: tuple[str, ...]
    affected_files: dict[str, tuple[str, ...]]

    @classmethod
    def from_prepared(cls, prepared: PreparedScenario) -> "ScenarioPreparationEvidence":
        impact = prepared.impact
        return cls(
            scenario=prepared.fixture.scenario.value,
            provider_mode=prepared.fixture.provider_mode,
            requirement_sha256=hashlib.sha256(
                prepared.fixture.requirement.encode("utf-8")
            ).hexdigest(),
            seed_sha256=prepared.seed_sha256,
            files=prepared.files,
            affected_files=impact.affected_files if impact else {},
        )
