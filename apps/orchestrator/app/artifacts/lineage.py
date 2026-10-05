"""Typed, cycle-safe queries over immutable artifact versions."""

import uuid
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.models import Artifact, ArtifactLineage, WorkflowRun


class LineageRelationship(StrEnum):
    DERIVED_FROM = "DERIVED_FROM"
    IMPLEMENTS = "IMPLEMENTS"
    VALIDATES = "VALIDATES"
    DOCUMENTS = "DOCUMENTS"
    SUPERSEDES = "SUPERSEDES"


@dataclass(frozen=True)
class LineageArtifact:
    id: uuid.UUID
    workflow_id: uuid.UUID
    logical_name: str
    artifact_type: str
    version: int
    sha256: str
    schema_version: str
    producer_stage_run_id: uuid.UUID | None
    requirement_ids: tuple[str, ...]
    component_ids: tuple[str, ...]

    @classmethod
    def from_record(cls, artifact: Artifact) -> "LineageArtifact":
        return cls(
            id=artifact.id,
            workflow_id=artifact.workflow_id,
            logical_name=artifact.logical_name,
            artifact_type=artifact.artifact_type,
            version=artifact.version,
            sha256=artifact.content_sha256,
            schema_version=artifact.schema_version,
            producer_stage_run_id=artifact.producer_stage_run_id,
            requirement_ids=tuple(artifact.requirement_ids),
            component_ids=tuple(artifact.component_ids),
        )


@dataclass(frozen=True)
class LineageConnection:
    edge_id: uuid.UUID
    relationship: LineageRelationship
    parent: LineageArtifact
    child: LineageArtifact
    requirement_ids: tuple[str, ...]
    component_ids: tuple[str, ...]


@dataclass(frozen=True)
class LineageDescendant:
    artifact: LineageArtifact
    depth: int


class ArtifactLineageService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_relationship(
        self,
        workflow_id: uuid.UUID,
        *,
        parent_artifact_id: uuid.UUID,
        child_artifact_id: uuid.UUID,
        relationship: LineageRelationship | str,
        requirement_ids: list[str] | None = None,
        component_ids: list[str] | None = None,
    ) -> ArtifactLineage:
        try:
            kind = LineageRelationship(relationship)
        except ValueError as error:
            raise ValueError(f"Unknown lineage relationship: {relationship}") from error
        if parent_artifact_id == child_artifact_id:
            raise ValueError("Lineage parent and child must differ")
        # Match artifact/audit lock order before INSERT takes a foreign-key share lock.
        # Concurrent fan-out stages would otherwise deadlock upgrading to the audit lock.
        workflow = await self.session.scalar(
            select(WorkflowRun).where(WorkflowRun.id == workflow_id).with_for_update()
        )
        if workflow is None:
            raise KeyError(f"Unknown workflow {workflow_id}")
        parent = await self._require_artifact(workflow_id, parent_artifact_id)
        child = await self._require_artifact(workflow_id, child_artifact_id)
        existing = await self.session.scalar(
            select(ArtifactLineage).where(
                ArtifactLineage.workflow_id == workflow_id,
                ArtifactLineage.parent_artifact_id == parent_artifact_id,
                ArtifactLineage.child_artifact_id == child_artifact_id,
                ArtifactLineage.relationship == kind.value,
            )
        )
        if existing is not None:
            return existing
        if kind is LineageRelationship.SUPERSEDES and (
            parent.logical_name != child.logical_name or child.version <= parent.version
        ):
            raise ValueError("SUPERSEDES requires a newer version of the same logical artifact")
        descendants = await self.transitive_descendants(workflow_id, child_artifact_id)
        if any(item.artifact.id == parent_artifact_id for item in descendants):
            raise ValueError("Artifact lineage cycle detected")
        edge = ArtifactLineage(
            workflow_id=workflow_id,
            parent_artifact_id=parent_artifact_id,
            child_artifact_id=child_artifact_id,
            relationship=kind.value,
            requirement_ids=sorted(set(requirement_ids or [])),
            component_ids=sorted(set(component_ids or [])),
        )
        self.session.add(edge)
        await self.session.flush()
        return edge

    async def parents(
        self, workflow_id: uuid.UUID, artifact_id: uuid.UUID
    ) -> tuple[LineageConnection, ...]:
        child = await self._require_artifact(workflow_id, artifact_id)
        rows = (
            await self.session.execute(
                select(ArtifactLineage, Artifact)
                .join(Artifact, Artifact.id == ArtifactLineage.parent_artifact_id)
                .where(
                    ArtifactLineage.workflow_id == workflow_id,
                    ArtifactLineage.child_artifact_id == artifact_id,
                )
                .order_by(
                    Artifact.logical_name,
                    Artifact.version,
                    ArtifactLineage.relationship,
                    ArtifactLineage.id,
                )
            )
        ).all()
        return tuple(self._connection(edge, parent, child) for edge, parent in rows)

    async def children(
        self, workflow_id: uuid.UUID, artifact_id: uuid.UUID
    ) -> tuple[LineageConnection, ...]:
        parent = await self._require_artifact(workflow_id, artifact_id)
        rows = (
            await self.session.execute(
                select(ArtifactLineage, Artifact)
                .join(Artifact, Artifact.id == ArtifactLineage.child_artifact_id)
                .where(
                    ArtifactLineage.workflow_id == workflow_id,
                    ArtifactLineage.parent_artifact_id == artifact_id,
                )
                .order_by(
                    Artifact.logical_name,
                    Artifact.version,
                    ArtifactLineage.relationship,
                    ArtifactLineage.id,
                )
            )
        ).all()
        return tuple(self._connection(edge, parent, child) for edge, child in rows)

    async def transitive_descendants(
        self, workflow_id: uuid.UUID, artifact_id: uuid.UUID
    ) -> tuple[LineageDescendant, ...]:
        await self._require_artifact(workflow_id, artifact_id)
        visited = {artifact_id}
        frontier = {artifact_id}
        depth = 0
        descendants: list[LineageDescendant] = []
        while frontier:
            depth += 1
            rows = (
                await self.session.scalars(
                    select(Artifact)
                    .join(
                        ArtifactLineage,
                        Artifact.id == ArtifactLineage.child_artifact_id,
                    )
                    .where(
                        ArtifactLineage.workflow_id == workflow_id,
                        ArtifactLineage.parent_artifact_id.in_(frontier),
                        Artifact.id.not_in(visited),
                    )
                    .order_by(Artifact.logical_name, Artifact.version, Artifact.id)
                )
            ).all()
            next_frontier: set[uuid.UUID] = set()
            for artifact in rows:
                if artifact.id in visited:
                    continue
                visited.add(artifact.id)
                next_frontier.add(artifact.id)
                descendants.append(LineageDescendant(LineageArtifact.from_record(artifact), depth))
            frontier = next_frontier
        return tuple(descendants)

    async def _require_artifact(self, workflow_id: uuid.UUID, artifact_id: uuid.UUID) -> Artifact:
        artifact = await self.session.scalar(
            select(Artifact).where(
                Artifact.id == artifact_id,
                Artifact.workflow_id == workflow_id,
            )
        )
        if artifact is None:
            raise ValueError("Lineage artifacts must belong to the workflow")
        return artifact

    @staticmethod
    def _connection(edge: ArtifactLineage, parent: Artifact, child: Artifact) -> LineageConnection:
        return LineageConnection(
            edge_id=edge.id,
            relationship=LineageRelationship(edge.relationship),
            parent=LineageArtifact.from_record(parent),
            child=LineageArtifact.from_record(child),
            requirement_ids=tuple(edge.requirement_ids),
            component_ids=tuple(edge.component_ids),
        )
