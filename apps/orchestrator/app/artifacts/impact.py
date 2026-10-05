"""Compute the artifact closure affected by an immutable upstream change."""

import uuid
from dataclasses import dataclass

from app.artifacts.lineage import ArtifactLineageService, LineageDescendant


@dataclass(frozen=True)
class ArtifactImpact:
    root_artifact_id: uuid.UUID
    descendants: tuple[LineageDescendant, ...]

    @property
    def artifact_ids(self) -> tuple[uuid.UUID, ...]:
        return tuple(item.artifact.id for item in self.descendants)

    @property
    def producer_stage_run_ids(self) -> tuple[uuid.UUID, ...]:
        return tuple(
            dict.fromkeys(
                item.artifact.producer_stage_run_id
                for item in self.descendants
                if item.artifact.producer_stage_run_id is not None
            )
        )


class ArtifactImpactAnalyzer:
    def __init__(self, lineage: ArtifactLineageService) -> None:
        self.lineage = lineage

    async def downstream(self, workflow_id: uuid.UUID, artifact_id: uuid.UUID) -> ArtifactImpact:
        return ArtifactImpact(
            root_artifact_id=artifact_id,
            descendants=await self.lineage.transitive_descendants(workflow_id, artifact_id),
        )
