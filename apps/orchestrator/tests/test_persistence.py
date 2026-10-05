"""Round trips, constraints, audit ordering and atomic persistence on PostgreSQL."""

import asyncio
import uuid

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.artifacts.schemas import ArtifactInput, ArtifactRef
from app.governance.approvals import ApprovalType
from app.orchestration.commands import TransitionContext
from app.orchestration.contracts import ScenarioType, StageStatus, WorkflowStatus
from app.orchestration.orchestrator import WorkflowOrchestrator
from app.persistence.models import (
    Approval,
    ArtifactLineage,
    AuditEvent,
    Decision,
    StageRun,
    WorkflowRun,
)
from app.persistence.service import WorkflowPersistenceService
from app.persistence.session import create_session_factory
from app.persistence.unit_of_work import UnitOfWork


def test_status_vocabularies_are_explicit() -> None:
    assert {member.value for member in ScenarioType} == {"GREENFIELD", "BROWNFIELD", "AMBIGUOUS"}
    assert {member.value for member in WorkflowStatus} == {
        "CREATED",
        "RUNNING",
        "WAITING_FOR_CLARIFICATION",
        "WAITING_FOR_APPROVAL",
        "REPLANNING",
        "SAFE_STOPPED",
        "COMPLETED",
        "FAILED",
        "CANCELLED",
    }
    assert {member.value for member in StageStatus} == {
        "PENDING",
        "BLOCKED",
        "READY",
        "RUNNING",
        "WAITING_APPROVAL",
        "SUCCEEDED",
        "FAILED",
        "RETRY_PENDING",
        "FALLBACK_RUNNING",
        "ROLLED_BACK",
        "STALE",
        "SKIPPED",
        "SAFE_STOPPED",
        "CANCELLED",
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_all_entities_round_trip_and_reload(
    phase6_factory: async_sessionmaker[AsyncSession], postgres_dsn: str
) -> None:
    service = WorkflowPersistenceService(phase6_factory)
    workflow_id = await service.create_workflow(
        scenario_type=ScenarioType.GREENFIELD,
        provider_mode="fake",
        workspace_ref="workspaces/greenfield/example",
    )
    first_stage_id = await service.add_stage_attempt(
        workflow_id, stage_name="requirements", generation=1, attempt=1, executor="agent"
    )
    first = await service.store_artifact(
        workflow_id,
        ArtifactInput(
            logical_name="requirements",
            artifact_type="requirements",
            schema_version="1",
            content={"title": "Short links", "version": 1},
            producer_stage_run_id=first_stage_id,
            requirement_ids=["REQ-1"],
            component_ids=["url-api"],
        ),
    )
    second = await service.store_artifact(
        workflow_id,
        ArtifactInput(
            logical_name="requirements",
            artifact_type="requirements",
            schema_version="1",
            content={"title": "Short links", "version": 2},
            producer_stage_run_id=first_stage_id,
            requirement_ids=["REQ-1"],
            component_ids=["url-api"],
        ),
    )
    second_stage_id = await service.add_stage_attempt(
        workflow_id,
        stage_name="requirements",
        generation=1,
        attempt=2,
        executor="agent",
        input_artifacts=[first],
    )
    edge_id = await service.link_artifacts(
        workflow_id,
        parent_artifact_id=first.id,
        child_artifact_id=second.id,
        relationship="SUPERSEDES",
        requirement_ids=["REQ-1"],
        component_ids=["url-api"],
    )
    decision_id = await service.record_decision(
        workflow_id,
        decision_type="API_SHAPE",
        outcome="HTTP_302",
        rationale="Preserve temporary redirect semantics",
        actor_type="HUMAN",
        actor_id="reviewer-1",
        related_artifact_ids=[second.id],
        requirement_ids=["REQ-1"],
    )
    await WorkflowOrchestrator(phase6_factory).transition_workflow(
        workflow_id,
        WorkflowStatus.RUNNING,
        TransitionContext(actor_type="SYSTEM", actor_id="orchestrator", expected_version=1),
    )
    approval_id = await service.request_approval(
        workflow_id,
        artifact_id=second.id,
        artifact_version=second.version,
        approval_type=ApprovalType.ARCHITECTURE,
        expected_workflow_version=2,
    )

    assert isinstance(workflow_id, uuid.UUID)
    assert first.version == 1
    assert second.version == 2
    assert first.sha256 != second.sha256

    # A new engine/session is a separate persistence lifecycle.
    engine = create_async_engine(make_url(postgres_dsn).set(drivername="postgresql+psycopg"))
    try:
        async with UnitOfWork.open(create_session_factory(engine)) as unit:
            workflow = await unit.workflows.get(workflow_id)
            first_stage = await unit.stages.get(first_stage_id)
            second_stage = await unit.stages.get(second_stage_id)
            artifact = await unit.artifacts.get_verified(second.id)
            edge = await unit.session.get(ArtifactLineage, edge_id)
            decision = await unit.session.get(Decision, decision_id)
            approval = await unit.session.get(Approval, approval_id)
            events = await unit.audit.page(workflow_id, limit=20)
            assert workflow.scenario_type == ScenarioType.GREENFIELD
            assert workflow.status == WorkflowStatus.WAITING_FOR_APPROVAL
            assert workflow.created_at.tzinfo is not None
            assert first_stage.attempt == 1
            assert second_stage.attempt == 2
            assert second_stage.input_artifact_refs == [
                {"id": str(first.id), "version": 1, "sha256": first.sha256}
            ]
            assert artifact.content == {"title": "Short links", "version": 2}
            assert artifact.requirement_ids == ["REQ-1"]
            assert edge is not None and edge.parent_artifact_id == first.id
            assert decision is not None and decision.related_artifact_ids == [str(second.id)]
            assert approval is not None and approval.artifact_hash == second.sha256
            assert approval.artifact_version == 2 and approval.status == "PENDING"
            assert [event.sequence for event in events] == list(range(1, 11))
            assert events[-2].event_type == "APPROVAL_REQUESTED"
            assert events[-1].event_type == "WORKFLOW_STATUS_CHANGED"
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_unique_attempt_and_exact_references(
    phase6_factory: async_sessionmaker[AsyncSession],
) -> None:
    service = WorkflowPersistenceService(phase6_factory)
    first_workflow = await service.create_workflow(
        scenario_type=ScenarioType.BROWNFIELD, provider_mode="fake", workspace_ref="one"
    )
    second_workflow = await service.create_workflow(
        scenario_type=ScenarioType.AMBIGUOUS, provider_mode="fake", workspace_ref="two"
    )
    await service.add_stage_attempt(
        first_workflow, stage_name="analysis", generation=1, attempt=1, executor="agent"
    )
    with pytest.raises(IntegrityError):
        await service.add_stage_attempt(
            first_workflow, stage_name="analysis", generation=1, attempt=1, executor="agent"
        )
    first_artifact = await service.store_artifact(
        first_workflow,
        ArtifactInput(
            logical_name="analysis",
            artifact_type="document",
            schema_version="1",
            content={"answer": 1},
        ),
    )
    second_artifact = await service.store_artifact(
        second_workflow,
        ArtifactInput(
            logical_name="analysis",
            artifact_type="document",
            schema_version="1",
            content={"answer": 2},
        ),
    )
    with pytest.raises(ValueError, match="exact version"):
        await service.add_stage_attempt(
            first_workflow,
            stage_name="design",
            generation=1,
            attempt=1,
            executor="agent",
            input_artifacts=[ArtifactRef(id=first_artifact.id, version=1, sha256="0" * 64)],
        )
    with pytest.raises(ValueError, match="belong to the workflow"):
        await service.link_artifacts(
            first_workflow,
            parent_artifact_id=first_artifact.id,
            child_artifact_id=second_artifact.id,
            relationship="DERIVED_FROM",
        )
    async with UnitOfWork.open(phase6_factory) as unit:
        attempts = await unit.session.scalar(
            select(func.count()).select_from(StageRun).where(StageRun.workflow_id == first_workflow)
        )
        assert attempts == 1
        assert (
            await unit.session.scalar(
                select(func.count())
                .select_from(ArtifactLineage)
                .where(ArtifactLineage.workflow_id == first_workflow)
            )
            == 0
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_atomic_rollback_and_foreign_keys(
    phase6_factory: async_sessionmaker[AsyncSession],
) -> None:
    workflow_id: uuid.UUID | None = None
    with pytest.raises(RuntimeError, match="abort"):
        async with UnitOfWork.open(phase6_factory) as unit:
            workflow = await unit.workflows.create(
                scenario_type=ScenarioType.GREENFIELD,
                provider_mode="fake",
                workspace_ref="rollback",
            )
            workflow_id = workflow.id
            await unit.audit.append(
                workflow_id, event_type="CREATED", actor_type="SYSTEM", actor_id="orchestrator"
            )
            raise RuntimeError("abort")
    async with UnitOfWork.open(phase6_factory) as unit:
        assert await unit.session.get(WorkflowRun, workflow_id) is None
        assert (
            await unit.session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.workflow_id == workflow_id)
            )
            == 0
        )

    with pytest.raises(IntegrityError):
        async with UnitOfWork.open(phase6_factory) as unit:
            unit.session.add(
                StageRun(
                    workflow_id=uuid.uuid4(),
                    stage_name="orphan",
                    generation=1,
                    attempt=1,
                    _status=StageStatus.PENDING,
                    executor="agent",
                    input_artifact_refs=[],
                    version=1,
                )
            )
            await unit.session.flush()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_audit_pages_remain_causal_under_concurrent_appends(
    phase6_factory: async_sessionmaker[AsyncSession],
) -> None:
    service = WorkflowPersistenceService(phase6_factory)
    workflow_id = await service.create_workflow(
        scenario_type=ScenarioType.GREENFIELD, provider_mode="fake", workspace_ref="audit"
    )

    async def append_event(index: int) -> None:
        async with UnitOfWork.open(phase6_factory) as unit:
            await unit.audit.append(
                workflow_id,
                event_type="PROBE",
                actor_type="SYSTEM",
                actor_id="test",
                payload={"index": index},
            )

    await asyncio.gather(*(append_event(index) for index in range(5)))
    async with UnitOfWork.open(phase6_factory) as unit:
        first = await unit.audit.page(workflow_id, limit=3)
        second = await unit.audit.page(workflow_id, after_sequence=3, limit=3)
        assert [event.sequence for event in first] == [1, 2, 3]
        assert [event.sequence for event in second] == [4, 5, 6]
        assert {event.payload["index"] for event in first[1:] + second} == set(range(5))


@pytest.mark.integration
@pytest.mark.asyncio
async def test_approval_foreign_key_binds_hash_and_version(
    phase6_factory: async_sessionmaker[AsyncSession],
) -> None:
    service = WorkflowPersistenceService(phase6_factory)
    workflow_id = await service.create_workflow(
        scenario_type=ScenarioType.GREENFIELD, provider_mode="fake", workspace_ref="approval"
    )
    artifact = await service.store_artifact(
        workflow_id,
        ArtifactInput(
            logical_name="design",
            artifact_type="document",
            schema_version="1",
            content={"design": "v1"},
        ),
    )
    with pytest.raises(IntegrityError):
        async with UnitOfWork.open(phase6_factory) as unit:
            await unit.session.execute(
                text(
                    "INSERT INTO approvals "
                    "(id, workflow_id, artifact_id, artifact_version, artifact_hash, "
                    "approval_type, status) "
                    "VALUES (:id, :workflow_id, :artifact_id, 1, :artifact_hash, "
                    "'DESIGN', 'PENDING')"
                ),
                {
                    "id": uuid.uuid4(),
                    "workflow_id": workflow_id,
                    "artifact_id": artifact.id,
                    "artifact_hash": "0" * 64,
                },
            )
