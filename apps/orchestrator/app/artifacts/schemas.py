"""Validated immutable artifact inputs and exact-version references."""

import uuid
from typing import Any

from pydantic import BaseModel, Field


class ArtifactInput(BaseModel):
    logical_name: str = Field(min_length=1, max_length=128)
    artifact_type: str = Field(min_length=1, max_length=128)
    schema_version: str = Field(min_length=1, max_length=64)
    content: dict[str, Any]
    requirement_ids: list[str] = Field(default_factory=list)
    component_ids: list[str] = Field(default_factory=list)
    producer_stage_run_id: uuid.UUID | None = None


class ArtifactRef(BaseModel):
    id: uuid.UUID
    version: int
    sha256: str
