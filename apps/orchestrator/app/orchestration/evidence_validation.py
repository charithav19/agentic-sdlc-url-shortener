"""Typed, immutable evidence consumed by deterministic stage gates."""

import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.artifacts.store import canonical_content
from app.orchestration.contracts import StageStatus


class EvidenceModel(BaseModel):
    """Strict evidence snapshots; gates never receive mutable ORM entities."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ArtifactEvidence(EvidenceModel):
    id: uuid.UUID
    version: int = Field(ge=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifact_type: str = Field(min_length=1)
    content: dict[str, Any]
    current: bool = True

    @property
    def reference(self) -> str:
        return f"artifact:{self.id}@{self.version}:{self.sha256}"


class ApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    INVALIDATED = "INVALIDATED"


class ApprovalEvidence(EvidenceModel):
    id: uuid.UUID
    approval_type: str = Field(min_length=1)
    status: ApprovalStatus
    artifact_id: uuid.UUID
    artifact_version: int = Field(ge=1)
    artifact_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @property
    def reference(self) -> str:
        return f"approval:{self.id}"

    def matches(self, artifact: ArtifactEvidence) -> bool:
        return (
            self.artifact_id == artifact.id
            and self.artifact_version == artifact.version
            and self.artifact_hash == artifact.sha256
        )


class StageEvidence(EvidenceModel):
    stage_name: str = Field(min_length=1)
    status: StageStatus
    generation: int = Field(ge=1)
    current: bool = True

    @property
    def reference(self) -> str:
        return f"stage:{self.stage_name}@generation:{self.generation}"


class PolicyViolationEvidence(EvidenceModel):
    rule_id: str = Field(min_length=1)
    blocking: bool
    active: bool = True

    @property
    def reference(self) -> str:
        return f"policy:{self.rule_id}"


class GateContext(EvidenceModel):
    requirement: ArtifactEvidence | None = None
    task_plan: ArtifactEvidence | None = None
    architecture: ArtifactEvidence | None = None
    approvals: tuple[ApprovalEvidence, ...] = ()
    stages: tuple[StageEvidence, ...] = ()
    policy_violations: tuple[PolicyViolationEvidence, ...] = ()


class InvalidEvidence(ValueError):
    """Evidence exists but is stale, corrupted, or schema-incompatible."""


def validate_artifact[OutputModel: BaseModel](
    artifact: ArtifactEvidence,
    schema: type[OutputModel],
    *,
    label: str,
) -> OutputModel:
    """Verify freshness, digest, and structured output before a gate trusts it."""

    if not artifact.current:
        raise InvalidEvidence(f"{label} artifact is stale")
    _, actual_digest = canonical_content(artifact.content)
    if actual_digest != artifact.sha256:
        raise InvalidEvidence(f"{label} artifact hash does not match its content")
    try:
        return schema.model_validate(artifact.content, strict=True)
    except ValidationError as error:
        raise InvalidEvidence(f"{label} artifact does not match {schema.__name__}") from error


def has_nonblank_values(values: list[str]) -> bool:
    return bool(values) and all(value.strip() for value in values)
