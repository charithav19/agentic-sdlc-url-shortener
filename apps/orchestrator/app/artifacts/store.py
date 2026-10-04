"""Create and verify immutable artifact versions."""

import hashlib
import json
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.artifacts.schemas import ArtifactInput
from app.persistence.models import Artifact, StageRun, WorkflowRun


def canonical_content(content: dict[str, Any]) -> tuple[dict[str, Any], str]:
    serialized = json.dumps(
        content, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    return json.loads(serialized), hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class ArtifactStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def put(self, workflow_id: uuid.UUID, artifact_input: ArtifactInput) -> Artifact:
        workflow = await self.session.scalar(
            select(WorkflowRun).where(WorkflowRun.id == workflow_id).with_for_update()
        )
        if workflow is None:
            raise KeyError(f"Unknown workflow {workflow_id}")
        if artifact_input.producer_stage_run_id is not None:
            stage = await self.session.get(StageRun, artifact_input.producer_stage_run_id)
            if stage is None or stage.workflow_id != workflow_id:
                raise ValueError("Producer stage must belong to the workflow")
        content, digest = canonical_content(artifact_input.content)
        last_version = await self.session.scalar(
            select(func.max(Artifact.version)).where(
                Artifact.workflow_id == workflow_id,
                Artifact.logical_name == artifact_input.logical_name,
            )
        )
        artifact = Artifact(
            workflow_id=workflow_id,
            logical_name=artifact_input.logical_name,
            artifact_type=artifact_input.artifact_type,
            version=(last_version or 0) + 1,
            content=content,
            content_sha256=digest,
            schema_version=artifact_input.schema_version,
            producer_stage_run_id=artifact_input.producer_stage_run_id,
            requirement_ids=list(artifact_input.requirement_ids),
            component_ids=list(artifact_input.component_ids),
        )
        self.session.add(artifact)
        await self.session.flush()
        return artifact

    async def get_verified(self, artifact_id: uuid.UUID) -> Artifact:
        artifact = await self.session.get(Artifact, artifact_id)
        if artifact is None:
            raise KeyError(f"Unknown artifact {artifact_id}")
        _, digest = canonical_content(artifact.content)
        if digest != artifact.content_sha256:
            raise ValueError("Artifact content hash mismatch")
        return artifact
