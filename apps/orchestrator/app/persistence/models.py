"""Phase 6 durable workflow, provenance and governance records."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    event,
    func,
    inspect,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm.attributes import NO_VALUE

from app.orchestration.contracts import ScenarioType, StageStatus, WorkflowStatus
from app.orchestration.state_authority import transition_is_authorized
from app.persistence.base import Base


def new_id() -> uuid.UUID:
    return uuid.uuid4()


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    __table_args__ = (
        CheckConstraint("generation > 0", name="ck_workflow_generation"),
        CheckConstraint("version > 0", name="ck_workflow_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    scenario_type: Mapped[ScenarioType] = mapped_column(
        Enum(ScenarioType, name="scenario_type", native_enum=False, create_constraint=True)
    )
    _status: Mapped[WorkflowStatus] = mapped_column(
        "status",
        Enum(WorkflowStatus, name="workflow_status", native_enum=False, create_constraint=True),
        default=WorkflowStatus.CREATED,
    )
    provider_mode: Mapped[str] = mapped_column(String(32))
    workspace_ref: Mapped[str] = mapped_column(String(1024))
    requirement_version: Mapped[int] = mapped_column(Integer, default=1)
    graph_revision_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    graph_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    generation: Mapped[int] = mapped_column(Integer, default=1)
    version: Mapped[int] = mapped_column(Integer, default=1)
    last_successful_stage: Mapped[str | None] = mapped_column(String(128), nullable=True)
    stop_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_human_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    @property
    def status(self) -> WorkflowStatus:
        return self._status


class StageRun(Base):
    __tablename__ = "stage_runs"
    __table_args__ = (
        UniqueConstraint(
            "workflow_id", "generation", "stage_name", "attempt", name="uq_stage_attempt"
        ),
        CheckConstraint("generation > 0", name="ck_stage_generation"),
        CheckConstraint("attempt > 0", name="ck_stage_attempt"),
        CheckConstraint("version > 0", name="ck_stage_version"),
        CheckConstraint(
            "execution_mode IN ('PRIMARY', 'FALLBACK')", name="ck_stage_execution_mode"
        ),
        Index("ix_stage_workflow_status", "workflow_id", "status"),
        Index(
            "uq_stage_active_claim",
            "workflow_id",
            "generation",
            "stage_name",
            unique=True,
            postgresql_where=text("lease_token IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workflow_runs.id", ondelete="RESTRICT")
    )
    stage_name: Mapped[str] = mapped_column(String(128))
    generation: Mapped[int] = mapped_column(Integer)
    attempt: Mapped[int] = mapped_column(Integer)
    _status: Mapped[StageStatus] = mapped_column(
        "status",
        Enum(StageStatus, name="stage_status", native_enum=False, create_constraint=True),
        default=StageStatus.PENDING,
    )
    executor: Mapped[str] = mapped_column(String(128))
    input_artifact_refs: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    lease_token: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    claim_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    retry_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    recommended_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_mode: Mapped[str] = mapped_column(String(16), default="PRIMARY")
    fallback_source_stage_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("stage_runs.id", ondelete="RESTRICT"), nullable=True
    )
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def status(self) -> StageStatus:
        return self._status


class Artifact(Base):
    __tablename__ = "artifacts"
    __table_args__ = (
        UniqueConstraint("workflow_id", "id", name="uq_artifact_workflow_id"),
        UniqueConstraint("workflow_id", "logical_name", "version", name="uq_artifact_version"),
        UniqueConstraint(
            "workflow_id", "id", "version", "content_sha256", name="uq_artifact_exact_ref"
        ),
        CheckConstraint("version > 0", name="ck_artifact_version"),
        CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'", name="ck_artifact_sha256"),
        Index("ix_artifact_workflow_name", "workflow_id", "logical_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workflow_runs.id", ondelete="RESTRICT")
    )
    logical_name: Mapped[str] = mapped_column(String(128))
    artifact_type: Mapped[str] = mapped_column(String(128))
    version: Mapped[int] = mapped_column(Integer)
    content: Mapped[dict[str, Any] | list[Any]] = mapped_column(JSONB)
    content_sha256: Mapped[str] = mapped_column(String(64))
    schema_version: Mapped[str] = mapped_column(String(64))
    producer_stage_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("stage_runs.id", ondelete="RESTRICT"), nullable=True
    )
    requirement_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    component_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ArtifactLifecycle(Base):
    __tablename__ = "artifact_lifecycle"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workflow_id", "artifact_id"],
            ["artifacts.workflow_id", "artifacts.id"],
            name="fk_artifact_lifecycle_exact_artifact",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "status IN ('CANDIDATE', 'APPROVED', 'ROLLED_BACK', 'STALE')",
            name="ck_artifact_lifecycle_status",
        ),
        CheckConstraint("version > 0", name="ck_artifact_lifecycle_version"),
        Index("ix_artifact_lifecycle_workflow_status", "workflow_id", "status"),
    )

    artifact_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    workflow_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    status: Mapped[str] = mapped_column(String(32))
    active: Mapped[bool] = mapped_column(default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CandidateReference(Base):
    __tablename__ = "candidate_references"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workflow_id", "active_artifact_id"],
            ["artifacts.workflow_id", "artifacts.id"],
            name="fk_candidate_ref_active",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["workflow_id", "approved_artifact_id"],
            ["artifacts.workflow_id", "artifacts.id"],
            name="fk_candidate_ref_approved",
            ondelete="RESTRICT",
        ),
        CheckConstraint("version > 0", name="ck_candidate_ref_version"),
    )

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workflow_runs.id", ondelete="RESTRICT"), primary_key=True
    )
    logical_name: Mapped[str] = mapped_column(String(128), primary_key=True)
    active_artifact_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    approved_artifact_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Compensation(Base):
    __tablename__ = "compensations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workflow_id", "candidate_artifact_id"],
            ["artifacts.workflow_id", "artifacts.id"],
            name="fk_compensation_candidate",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["workflow_id", "previous_approved_artifact_id"],
            ["artifacts.workflow_id", "artifacts.id"],
            name="fk_compensation_previous_approved",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["workflow_id", "restored_artifact_id"],
            ["artifacts.workflow_id", "artifacts.id"],
            name="fk_compensation_restored",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "workflow_id",
            "candidate_artifact_id",
            "cause_stage_run_id",
            name="uq_compensation_cause",
        ),
        CheckConstraint(
            "status IN ('STARTED', 'COMPLETED', 'FAILED')",
            name="ck_compensation_status",
        ),
        Index("ix_compensation_workflow_status", "workflow_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workflow_runs.id", ondelete="RESTRICT")
    )
    candidate_artifact_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    cause_stage_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("stage_runs.id", ondelete="RESTRICT")
    )
    previous_approved_artifact_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    restored_artifact_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="STARTED")
    failure_reason: Mapped[str] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ArtifactLineage(Base):
    __tablename__ = "artifact_lineage"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workflow_id", "parent_artifact_id"],
            ["artifacts.workflow_id", "artifacts.id"],
            name="fk_lineage_parent_workflow",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["workflow_id", "child_artifact_id"],
            ["artifacts.workflow_id", "artifacts.id"],
            name="fk_lineage_child_workflow",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "parent_artifact_id", "child_artifact_id", "relationship", name="uq_lineage_edge"
        ),
        CheckConstraint("parent_artifact_id <> child_artifact_id", name="ck_lineage_distinct"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workflow_runs.id", ondelete="RESTRICT")
    )
    parent_artifact_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    child_artifact_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    relationship: Mapped[str] = mapped_column(String(64))
    requirement_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    component_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Decision(Base):
    __tablename__ = "decisions"
    __table_args__ = (
        CheckConstraint(
            "actor_type IN ('SYSTEM', 'AGENT', 'HUMAN')", name="ck_decision_actor_type"
        ),
        Index("ix_decision_workflow_created", "workflow_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workflow_runs.id", ondelete="RESTRICT")
    )
    stage_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("stage_runs.id", ondelete="RESTRICT"), nullable=True
    )
    decision_type: Mapped[str] = mapped_column(String(128))
    outcome: Mapped[str] = mapped_column(String(128))
    rationale: Mapped[str] = mapped_column(Text)
    alternatives: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    actor_type: Mapped[str] = mapped_column(String(16))
    actor_id: Mapped[str] = mapped_column(String(128))
    related_artifact_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    requirement_ids: Mapped[list[str]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Approval(Base):
    __tablename__ = "approvals"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workflow_id", "artifact_id", "artifact_version", "artifact_hash"],
            [
                "artifacts.workflow_id",
                "artifacts.id",
                "artifacts.version",
                "artifacts.content_sha256",
            ],
            name="fk_approval_exact_artifact",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'REJECTED', 'INVALIDATED')",
            name="ck_approval_status",
        ),
        CheckConstraint(
            "approval_type IN ('ARCHITECTURE', 'HIGH_IMPACT_CHANGE', 'ASSUMPTION', 'RELEASE')",
            name="ck_approval_type",
        ),
        CheckConstraint("artifact_version > 0", name="ck_approval_artifact_version"),
        Index("ix_approval_workflow_status", "workflow_id", "status"),
        Index(
            "uq_approval_pending_exact",
            "workflow_id",
            "approval_type",
            "artifact_id",
            "artifact_version",
            unique=True,
            postgresql_where=text("status = 'PENDING'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workflow_runs.id", ondelete="RESTRICT")
    )
    artifact_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    artifact_version: Mapped[int] = mapped_column(Integer)
    artifact_hash: Mapped[str] = mapped_column(String(64))
    approval_type: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16), default="PENDING")
    reviewer_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        UniqueConstraint("workflow_id", "sequence", name="uq_audit_workflow_sequence"),
        CheckConstraint("sequence > 0", name="ck_audit_sequence"),
        CheckConstraint("actor_type IN ('SYSTEM', 'AGENT', 'HUMAN')", name="ck_audit_actor_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("workflow_runs.id", ondelete="RESTRICT")
    )
    stage_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("stage_runs.id", ondelete="RESTRICT"), nullable=True
    )
    sequence: Mapped[int] = mapped_column(BigInteger)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    trace_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    actor_type: Mapped[str] = mapped_column(String(16))
    actor_id: Mapped[str] = mapped_column(String(128))
    event_type: Mapped[str] = mapped_column(String(128))
    before_state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    after_state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    artifact_refs: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


def _guard_status_mutation(target: Any, value: Any, old_value: Any, _initiator: Any) -> Any:
    state = inspect(target)
    if old_value is NO_VALUE and (state.transient or state.pending):
        return value
    if old_value is value or old_value == value:
        return value
    if not transition_is_authorized():
        raise PermissionError("Only WorkflowOrchestrator may change persisted status")
    return value


event.listen(WorkflowRun._status, "set", _guard_status_mutation, retval=True)
event.listen(StageRun._status, "set", _guard_status_mutation, retval=True)
