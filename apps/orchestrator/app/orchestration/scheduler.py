"""Bounded asyncio scheduler for one durable workflow generation."""

import asyncio
import uuid
from collections.abc import Mapping
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings, get_settings
from app.orchestration.contracts import StageStatus, WorkflowStatus
from app.orchestration.graph import WorkflowGraph
from app.orchestration.joins import SynchronizationJoinCoordinator
from app.orchestration.orchestrator import WorkflowOrchestrator
from app.orchestration.readiness import ReadinessChange
from app.orchestration.recovery import RecoveryCoordinator, RecoveryResult
from app.orchestration.retries import RetryPlanner
from app.orchestration.worker import StageExecutor, StageWorker, StageWorkResult
from app.persistence.models import StageRun, WorkflowRun
from app.persistence.session import session_scope


@dataclass(frozen=True)
class SchedulerCycleResult:
    workflow_id: uuid.UUID
    readiness_before: tuple[ReadinessChange, ...]
    work: tuple[StageWorkResult, ...]
    readiness_after: tuple[ReadinessChange, ...]
    recovery: tuple[RecoveryResult, ...] = ()


class WorkflowScheduler:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        graph: WorkflowGraph,
        executors: Mapping[str, StageExecutor],
        *,
        max_parallel_stages: int = 3,
        lease_seconds: int = 300,
        scheduler_id: str | None = None,
        retry_planner: RetryPlanner | None = None,
    ) -> None:
        if max_parallel_stages < 1:
            raise ValueError("max_parallel_stages must be positive")
        if lease_seconds < 1:
            raise ValueError("lease_seconds must be positive")
        self.session_factory = session_factory
        self.graph = graph
        self.max_parallel_stages = max_parallel_stages
        self.scheduler_id = scheduler_id or f"scheduler-{uuid.uuid4()}"
        self.orchestrator = WorkflowOrchestrator(session_factory)
        self.joins = SynchronizationJoinCoordinator(graph, self.orchestrator)
        self.recovery = RecoveryCoordinator(
            session_factory,
            graph,
            self.orchestrator,
            retry_planner=retry_planner,
        )
        self.worker = StageWorker(
            self.orchestrator,
            executors,
            owner=self.scheduler_id,
            lease_seconds=lease_seconds,
        )

    @classmethod
    def configured(
        cls,
        session_factory: async_sessionmaker[AsyncSession],
        graph: WorkflowGraph,
        executors: Mapping[str, StageExecutor],
        *,
        settings: Settings | None = None,
        scheduler_id: str | None = None,
    ) -> "WorkflowScheduler":
        configured = settings or get_settings()
        return cls(
            session_factory,
            graph,
            executors,
            max_parallel_stages=configured.max_parallel_stages,
            lease_seconds=configured.stage_claim_lease_seconds,
            scheduler_id=scheduler_id,
        )

    async def run_cycle(self, workflow_id: uuid.UUID) -> SchedulerCycleResult:
        """Run the stages ready at cycle start, then recompute all joins."""

        trace_id = uuid.uuid4()
        before = await self.joins.synchronize(
            workflow_id, actor_id=self.scheduler_id, trace_id=trace_id
        )
        ready = await self._ready_stage_ids(workflow_id)
        semaphore = asyncio.Semaphore(self.max_parallel_stages)

        async def run_bounded(stage_run_id: uuid.UUID) -> StageWorkResult:
            async with semaphore:
                return await self.worker.run(stage_run_id)

        work = tuple(await asyncio.gather(*(run_bounded(stage_id) for stage_id in ready)))
        recovery: list[RecoveryResult] = []
        for item in work:
            if item.committed and item.succeeded is False and item.failure is not None:
                recovery.append(
                    await self.recovery.recover(
                        item.stage_run_id,
                        failure=item.failure,
                        failure_reason=item.error or item.failure.code.value,
                        actor_id=self.scheduler_id,
                        trace_id=trace_id,
                    )
                )
        after = await self.joins.synchronize(
            workflow_id, actor_id=self.scheduler_id, trace_id=trace_id
        )
        return SchedulerCycleResult(
            workflow_id=workflow_id,
            readiness_before=before.changes,
            work=work,
            readiness_after=after.changes,
            recovery=tuple(recovery),
        )

    async def _ready_stage_ids(self, workflow_id: uuid.UUID) -> tuple[uuid.UUID, ...]:
        async with session_scope(self.session_factory) as session:
            workflow = await session.get(WorkflowRun, workflow_id)
            if workflow is None:
                raise KeyError(f"Unknown workflow {workflow_id}")
            if workflow.status is not WorkflowStatus.RUNNING:
                return ()
            rows = list(
                await session.scalars(
                    select(StageRun)
                    .where(
                        StageRun.workflow_id == workflow_id,
                        StageRun.generation == workflow.generation,
                    )
                    .order_by(StageRun.stage_name, StageRun.attempt.desc())
                )
            )
            latest: dict[str, StageRun] = {}
            for stage in rows:
                latest.setdefault(stage.stage_name, stage)
            order = {name: index for index, name in enumerate(self.graph.topological_order)}
            ready = [
                stage
                for stage in latest.values()
                if stage.stage_name in order
                and stage.status is StageStatus.READY
                and stage.lease_token is None
            ]
            ready.sort(key=lambda stage: order[stage.stage_name])
            return tuple(stage.id for stage in ready)
