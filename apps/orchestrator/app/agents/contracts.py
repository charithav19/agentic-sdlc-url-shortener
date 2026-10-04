"""Immutable, serializable agent inputs with no database or workflow capabilities."""

import hashlib
import json
import uuid
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ToolName = Literal["read_artifact", "list_files", "read_file", "search_code"]


class Snapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str = Field(min_length=1, max_length=256)
    version: int = Field(ge=1)
    content: str = Field(max_length=64000)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content.encode()).hexdigest()


class FileSnapshot(Snapshot):
    @field_validator("name")
    @classmethod
    def safe_relative_name(cls, name: str) -> str:
        path = PurePosixPath(name)
        denied = {".git", ".ssh", ".aws", ".codex", ".env", "credentials"}
        if (
            path.is_absolute()
            or ".." in path.parts
            or "\\" in name
            or any(part in denied or part.startswith(".env.") for part in path.parts)
        ):
            raise ValueError("Only non-secret relative snapshot paths are allowed")
        return name


class AgentContext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    workflow_id: uuid.UUID
    stage_run_id: uuid.UUID
    generation: int = Field(ge=1)
    attempt: int = Field(ge=1)
    trace_id: uuid.UUID
    requirement: str = Field(min_length=1, max_length=32000)
    artifacts: tuple[Snapshot, ...] = Field(default=(), max_length=64)
    files: tuple[FileSnapshot, ...] = Field(default=(), max_length=128)
    authorized_tools: tuple[ToolName, ...] = ()

    @model_validator(mode="after")
    def unique_and_bounded(self) -> Self:
        for values in (self.artifacts, self.files):
            if len({value.name for value in values}) != len(values):
                raise ValueError("Snapshot names must be unique")
        if len(set(self.authorized_tools)) != len(self.authorized_tools):
            raise ValueError("Duplicate authorized tools")
        if sum(len(item.content) for item in (*self.artifacts, *self.files)) > 256000:
            raise ValueError("Context snapshot budget exceeded")
        return self


@dataclass(frozen=True)
class Specialist[T: BaseModel]:
    name: str
    instructions: str
    output_type: type[T]
    allowed_tools: tuple[ToolName, ...]
    max_turns: int = 6
    timeout_seconds: float = 60
    instruction_version: str = "1"
    schema_version: str = "1"


class AgentResult[T: BaseModel](BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    output: T
    provider: Literal["openai", "fake"]
    model: str
    sdk_version: str
    specialist: str
    instruction_version: str
    schema_version: str
    instruction_sha256: str
    schema_sha256: str
    context_sha256: str
    workflow_id: uuid.UUID
    stage_run_id: uuid.UUID
    trace_id: uuid.UUID
    generation: int
    attempt: int
    max_turns: int
    timeout_seconds: float


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
