"""Database-enforced immutable artifacts and append-only audit events."""

import asyncio
import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.artifacts.schemas import ArtifactInput
from app.artifacts.store import canonical_content
from app.orchestration.contracts import ScenarioType
from app.persistence.models import Artifact, AuditEvent
from app.persistence.service import WorkflowPersistenceService
from app.persistence.unit_of_work import UnitOfWork


def test_canonical_hash_is_stable_and_rejects_non_json_numbers() -> None:
    first, first_hash = canonical_content({"b": 2, "a": {"x": 1}})
    second, second_hash = canonical_content({"a": {"x": 1}, "b": 2})
    assert first == second
    assert first_hash == second_hash
    with pytest.raises(ValueError):
        canonical_content({"invalid": float("nan")})


@pytest.mark.integration
@pytest.mark.asyncio
async def test_artifacts_and_audit_are_append_only_in_postgresql(
    phase6_factory: async_sessionmaker[AsyncSession],
) -> None:
    service = WorkflowPersistenceService(phase6_factory)
    workflow_id = await service.create_workflow(
        scenario_type=ScenarioType.GREENFIELD, provider_mode="fake", workspace_ref="immutable"
    )
    first = await service.store_artifact(
        workflow_id,
        ArtifactInput(
            logical_name="design",
            artifact_type="document",
            schema_version="1",
            content={"decision": "old"},
        ),
    )
    second = await service.store_artifact(
        workflow_id,
        ArtifactInput(
            logical_name="design",
            artifact_type="document",
            schema_version="1",
            content={"decision": "new"},
        ),
    )
    assert (first.version, second.version) == (1, 2)
    async with UnitOfWork.open(phase6_factory) as unit:
        event = (await unit.audit.page(workflow_id, limit=1))[0]
        assert event.sequence == 1

    mutations = [
        (
            "UPDATE artifacts SET content_sha256 = :digest WHERE id = :id",
            {"id": first.id, "digest": "0" * 64},
        ),
        ("DELETE FROM artifacts WHERE id = :id", {"id": first.id}),
        ("UPDATE audit_events SET event_type = 'FORGED' WHERE id = :id", {"id": event.id}),
        ("DELETE FROM audit_events WHERE id = :id", {"id": event.id}),
        ("TRUNCATE audit_events", {}),
    ]
    for statement, parameters in mutations:
        with pytest.raises(DBAPIError, match="append-only"):
            async with UnitOfWork.open(phase6_factory) as unit:
                await unit.session.execute(text(statement), parameters)

    async with UnitOfWork.open(phase6_factory) as unit:
        old = await unit.artifacts.get_verified(first.id)
        new = await unit.artifacts.get_verified(second.id)
        retained_event = await unit.session.get(AuditEvent, event.id)
        assert old.content == {"decision": "old"}
        assert new.content == {"decision": "new"}
        assert retained_event is not None and retained_event.event_type == "WORKFLOW_CREATED"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_versions_never_overwrite(
    phase6_factory: async_sessionmaker[AsyncSession],
) -> None:
    service = WorkflowPersistenceService(phase6_factory)
    workflow_id = await service.create_workflow(
        scenario_type=ScenarioType.GREENFIELD, provider_mode="fake", workspace_ref="versions"
    )

    async def store(index: int) -> uuid.UUID:
        ref = await service.store_artifact(
            workflow_id,
            ArtifactInput(
                logical_name="design",
                artifact_type="document",
                schema_version="1",
                content={"index": index},
            ),
        )
        return ref.id

    ids = await asyncio.gather(*(store(index) for index in range(5)))
    assert len(set(ids)) == 5
    async with UnitOfWork.open(phase6_factory) as unit:
        artifacts = (
            await unit.session.scalars(
                select(Artifact)
                .where(Artifact.workflow_id == workflow_id)
                .order_by(Artifact.version)
            )
        ).all()
        assert [artifact.version for artifact in artifacts] == [1, 2, 3, 4, 5]
        assert {artifact.content["index"] for artifact in artifacts} == set(range(5))
