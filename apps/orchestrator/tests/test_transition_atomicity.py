"""Status mutation and audit insertion form one transaction."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.observability.audit_store import AuditStore
from app.orchestration.commands import TransitionContext
from app.orchestration.contracts import ScenarioType, StageStatus, WorkflowStatus
from app.orchestration.orchestrator import WorkflowOrchestrator
from app.orchestration.state_machine import StaleTransitionError
from app.persistence.service import WorkflowPersistenceService
from app.persistence.unit_of_work import UnitOfWork


class FailingAuditStore(AuditStore):
    async def append(self, *args, **kwargs):
        raise RuntimeError("injected audit failure")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_audit_failure_rolls_back_stage_transition(
    phase6_factory: async_sessionmaker[AsyncSession],
) -> None:
    persistence = WorkflowPersistenceService(phase6_factory)
    workflow_id = await persistence.create_workflow(
        scenario_type=ScenarioType.GREENFIELD,
        provider_mode="fake",
        workspace_ref="atomic-transition",
    )
    stage_id = await persistence.add_stage_attempt(
        workflow_id,
        stage_name="INTAKE",
        generation=1,
        attempt=1,
        executor="intake",
    )
    orchestrator = WorkflowOrchestrator(phase6_factory, audit_store_factory=FailingAuditStore)

    with pytest.raises(RuntimeError, match="injected audit failure"):
        await orchestrator.transition_stage(
            stage_id,
            StageStatus.BLOCKED,
            TransitionContext(actor_type="SYSTEM", actor_id="orchestrator"),
        )

    async with UnitOfWork.open(phase6_factory) as unit:
        stage = await unit.stages.get(stage_id)
        events = await unit.audit.page(workflow_id)
        assert stage.status == StageStatus.PENDING
        assert stage.version == 1
        assert all(event.event_type != "STAGE_STATUS_CHANGED" for event in events)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_stale_version_rejected_without_state_or_audit_change(
    phase6_factory: async_sessionmaker[AsyncSession],
) -> None:
    persistence = WorkflowPersistenceService(phase6_factory)
    workflow_id = await persistence.create_workflow(
        scenario_type=ScenarioType.GREENFIELD,
        provider_mode="fake",
        workspace_ref="stale-transition",
    )
    stage_id = await persistence.add_stage_attempt(
        workflow_id,
        stage_name="INTAKE",
        generation=1,
        attempt=1,
        executor="intake",
    )
    orchestrator = WorkflowOrchestrator(phase6_factory)

    with pytest.raises(StaleTransitionError, match="expected 2, current 1"):
        await orchestrator.transition_stage(
            stage_id,
            StageStatus.BLOCKED,
            TransitionContext(
                actor_type="SYSTEM",
                actor_id="orchestrator",
                expected_version=2,
            ),
        )

    async with UnitOfWork.open(phase6_factory) as unit:
        stage = await unit.stages.get(stage_id)
        events = await unit.audit.page(workflow_id)
        assert stage.status == StageStatus.PENDING
        assert stage.version == 1
        assert all(event.event_type != "STAGE_STATUS_CHANGED" for event in events)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_direct_status_mutation_is_blocked(
    phase6_factory: async_sessionmaker[AsyncSession],
) -> None:
    persistence = WorkflowPersistenceService(phase6_factory)
    workflow_id = await persistence.create_workflow(
        scenario_type=ScenarioType.GREENFIELD,
        provider_mode="fake",
        workspace_ref="authority-boundary",
    )
    stage_id = await persistence.add_stage_attempt(
        workflow_id,
        stage_name="INTAKE",
        generation=1,
        attempt=1,
        executor="intake",
    )

    async with UnitOfWork.open(phase6_factory) as unit:
        workflow = await unit.workflows.get(workflow_id)
        stage = await unit.stages.get(stage_id)
        with pytest.raises(AttributeError):
            workflow.status = workflow.status.RUNNING
        with pytest.raises(PermissionError, match="Only WorkflowOrchestrator"):
            workflow._status = WorkflowStatus.RUNNING
        with pytest.raises(PermissionError, match="Only WorkflowOrchestrator"):
            stage._status = StageStatus.BLOCKED
        unit.session.expire(stage, ["_status"])
        with pytest.raises(PermissionError, match="Only WorkflowOrchestrator"):
            stage._status = StageStatus.BLOCKED


def test_agent_cannot_be_transition_actor() -> None:
    with pytest.raises(ValueError, match="Only SYSTEM or HUMAN"):
        TransitionContext(actor_type="AGENT", actor_id="agent-1")  # type: ignore[arg-type]
