"""Lifecycle metadata and active/approved pointers for implementation candidates."""

import uuid
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.governance.approvals import ApprovalStatus
from app.orchestration.contracts import StageStatus
from app.persistence.models import (
    Approval,
    Artifact,
    ArtifactLifecycle,
    CandidateReference,
    StageRun,
)


class ArtifactStatus(StrEnum):
    CANDIDATE = "CANDIDATE"
    APPROVED = "APPROVED"
    ROLLED_BACK = "ROLLED_BACK"
    STALE = "STALE"


class CandidateReferenceStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def activate_approved(
        self, workflow_id: uuid.UUID, artifact_id: uuid.UUID
    ) -> CandidateReference:
        artifact = await self._artifact(workflow_id, artifact_id)
        approval = await self.session.scalar(
            select(Approval)
            .where(
                Approval.workflow_id == workflow_id,
                Approval.artifact_id == artifact_id,
                Approval.artifact_version == artifact.version,
                Approval.artifact_hash == artifact.content_sha256,
                Approval.status == ApprovalStatus.APPROVED.value,
            )
            .limit(1)
        )
        if approval is None:
            raise ValueError("An exact approved artifact is required before activation")
        reference = await self._reference(workflow_id, artifact.logical_name)
        if reference is None:
            reference = CandidateReference(
                workflow_id=workflow_id,
                logical_name=artifact.logical_name,
                active_artifact_id=artifact.id,
                approved_artifact_id=artifact.id,
                version=1,
            )
            self.session.add(reference)
        else:
            await self._deactivate(reference.active_artifact_id)
            reference.active_artifact_id = artifact.id
            reference.approved_artifact_id = artifact.id
            reference.version += 1
        lifecycle = await self._lifecycle(artifact.id)
        if lifecycle is None:
            lifecycle = ArtifactLifecycle(
                artifact_id=artifact.id,
                workflow_id=workflow_id,
                status=ArtifactStatus.APPROVED.value,
                active=True,
                version=1,
            )
            self.session.add(lifecycle)
        else:
            lifecycle.status = ArtifactStatus.APPROVED.value
            lifecycle.active = True
            lifecycle.version += 1
        await self.session.flush()
        return reference

    async def stage_for_validation(
        self, workflow_id: uuid.UUID, artifact_id: uuid.UUID
    ) -> CandidateReference:
        artifact = await self._artifact(workflow_id, artifact_id)
        if artifact.producer_stage_run_id is None:
            raise ValueError("An implementation candidate requires a producer stage")
        producer = await self.session.get(StageRun, artifact.producer_stage_run_id)
        if (
            producer is None
            or producer.workflow_id != workflow_id
            or producer.stage_name != "IMPLEMENTATION"
            or producer.status is not StageStatus.SUCCEEDED
        ):
            raise ValueError("Candidate producer must be a succeeded IMPLEMENTATION stage")
        reference = await self._reference(workflow_id, artifact.logical_name)
        if reference is None:
            reference = CandidateReference(
                workflow_id=workflow_id,
                logical_name=artifact.logical_name,
                active_artifact_id=artifact.id,
                approved_artifact_id=None,
                version=1,
            )
            self.session.add(reference)
        elif reference.active_artifact_id != artifact.id:
            await self._deactivate(reference.active_artifact_id)
            reference.active_artifact_id = artifact.id
            reference.version += 1
        lifecycle = await self._lifecycle(artifact.id)
        if lifecycle is None:
            lifecycle = ArtifactLifecycle(
                artifact_id=artifact.id,
                workflow_id=workflow_id,
                status=ArtifactStatus.CANDIDATE.value,
                active=True,
                version=1,
            )
            self.session.add(lifecycle)
        else:
            lifecycle.status = ArtifactStatus.CANDIDATE.value
            lifecycle.active = True
            lifecycle.version += 1
        await self.session.flush()
        return reference

    async def _reference(
        self, workflow_id: uuid.UUID, logical_name: str
    ) -> CandidateReference | None:
        return await self.session.scalar(
            select(CandidateReference)
            .where(
                CandidateReference.workflow_id == workflow_id,
                CandidateReference.logical_name == logical_name,
            )
            .with_for_update()
        )

    async def _artifact(self, workflow_id: uuid.UUID, artifact_id: uuid.UUID) -> Artifact:
        artifact = await self.session.scalar(
            select(Artifact)
            .where(Artifact.id == artifact_id, Artifact.workflow_id == workflow_id)
            .with_for_update()
        )
        if artifact is None:
            raise KeyError(f"Unknown workflow artifact {artifact_id}")
        return artifact

    async def _lifecycle(self, artifact_id: uuid.UUID) -> ArtifactLifecycle | None:
        return await self.session.scalar(
            select(ArtifactLifecycle)
            .where(ArtifactLifecycle.artifact_id == artifact_id)
            .with_for_update()
        )

    async def _deactivate(self, artifact_id: uuid.UUID | None) -> None:
        if artifact_id is None:
            return
        lifecycle = await self._lifecycle(artifact_id)
        if lifecycle is not None and lifecycle.active:
            lifecycle.active = False
            lifecycle.version += 1
