"""Persist workflow execution and provenance foundations.

Revision ID: 0002_workflow_foundation
Revises: 0001_database_baseline
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002_workflow_foundation"
down_revision: str | None = "0001_database_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workflow_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "scenario_type",
            sa.Enum(
                "GREENFIELD",
                "BROWNFIELD",
                "AMBIGUOUS",
                name="scenario_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "CREATED",
                "RUNNING",
                "WAITING_FOR_CLARIFICATION",
                "WAITING_FOR_APPROVAL",
                "REPLANNING",
                "SAFE_STOPPED",
                "COMPLETED",
                "FAILED",
                "CANCELLED",
                name="workflow_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("provider_mode", sa.String(length=32), nullable=False),
        sa.Column("workspace_ref", sa.String(length=1024), nullable=False),
        sa.Column("requirement_version", sa.Integer(), nullable=False),
        sa.Column("graph_revision_id", sa.Uuid(), nullable=True),
        sa.Column("graph_hash", sa.String(length=64), nullable=True),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("last_successful_stage", sa.String(length=128), nullable=True),
        sa.Column("stop_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("generation > 0", name="ck_workflow_generation"),
        sa.CheckConstraint("version > 0", name="ck_workflow_version"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "stage_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("stage_name", sa.String(length=128), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
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
                name="stage_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("executor", sa.String(length=128), nullable=False),
        sa.Column("input_artifact_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("lease_token", sa.Uuid(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("attempt > 0", name="ck_stage_attempt"),
        sa.CheckConstraint("generation > 0", name="ck_stage_generation"),
        sa.CheckConstraint("version > 0", name="ck_stage_version"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflow_runs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workflow_id", "generation", "stage_name", "attempt", name="uq_stage_attempt"
        ),
    )
    op.create_index(
        "ix_stage_workflow_status", "stage_runs", ["workflow_id", "status"], unique=False
    )
    op.create_table(
        "artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("logical_name", sa.String(length=128), nullable=False),
        sa.Column("artifact_type", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("schema_version", sa.String(length=64), nullable=False),
        sa.Column("producer_stage_run_id", sa.Uuid(), nullable=True),
        sa.Column("requirement_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("component_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'", name="ck_artifact_sha256"),
        sa.CheckConstraint("version > 0", name="ck_artifact_version"),
        sa.ForeignKeyConstraint(["producer_stage_run_id"], ["stage_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflow_runs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workflow_id", "id", "version", "content_sha256", name="uq_artifact_exact_ref"
        ),
        sa.UniqueConstraint("workflow_id", "id", name="uq_artifact_workflow_id"),
        sa.UniqueConstraint("workflow_id", "logical_name", "version", name="uq_artifact_version"),
    )
    op.create_index(
        "ix_artifact_workflow_name", "artifacts", ["workflow_id", "logical_name"], unique=False
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("stage_run_id", sa.Uuid(), nullable=True),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("trace_id", sa.Uuid(), nullable=True),
        sa.Column("actor_type", sa.String(length=16), nullable=False),
        sa.Column("actor_id", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("before_state", sa.String(length=64), nullable=True),
        sa.Column("after_state", sa.String(length=64), nullable=True),
        sa.Column("artifact_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint(
            "actor_type IN ('SYSTEM', 'AGENT', 'HUMAN')", name="ck_audit_actor_type"
        ),
        sa.CheckConstraint("sequence > 0", name="ck_audit_sequence"),
        sa.ForeignKeyConstraint(["stage_run_id"], ["stage_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflow_runs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workflow_id", "sequence", name="uq_audit_workflow_sequence"),
    )
    op.create_table(
        "decisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("stage_run_id", sa.Uuid(), nullable=True),
        sa.Column("decision_type", sa.String(length=128), nullable=False),
        sa.Column("outcome", sa.String(length=128), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("alternatives", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("actor_type", sa.String(length=16), nullable=False),
        sa.Column("actor_id", sa.String(length=128), nullable=False),
        sa.Column("related_artifact_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("requirement_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "actor_type IN ('SYSTEM', 'AGENT', 'HUMAN')", name="ck_decision_actor_type"
        ),
        sa.ForeignKeyConstraint(["stage_run_id"], ["stage_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflow_runs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_decision_workflow_created", "decisions", ["workflow_id", "created_at"], unique=False
    )
    op.create_table(
        "approvals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_version", sa.Integer(), nullable=False),
        sa.Column("artifact_hash", sa.String(length=64), nullable=False),
        sa.Column("approval_type", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("reviewer_id", sa.String(length=128), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'REJECTED', 'INVALIDATED')",
            name="ck_approval_status",
        ),
        sa.ForeignKeyConstraint(
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
        sa.ForeignKeyConstraint(["workflow_id"], ["workflow_runs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_approval_workflow_status", "approvals", ["workflow_id", "status"], unique=False
    )
    op.create_table(
        "artifact_lineage",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("parent_artifact_id", sa.Uuid(), nullable=False),
        sa.Column("child_artifact_id", sa.Uuid(), nullable=False),
        sa.Column("relationship", sa.String(length=64), nullable=False),
        sa.Column("requirement_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("component_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("parent_artifact_id <> child_artifact_id", name="ck_lineage_distinct"),
        sa.ForeignKeyConstraint(
            ["workflow_id", "child_artifact_id"],
            ["artifacts.workflow_id", "artifacts.id"],
            name="fk_lineage_child_workflow",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id", "parent_artifact_id"],
            ["artifacts.workflow_id", "artifacts.id"],
            name="fk_lineage_parent_workflow",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflow_runs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "parent_artifact_id", "child_artifact_id", "relationship", name="uq_lineage_edge"
        ),
    )
    op.execute(
        """
        CREATE FUNCTION reject_append_only_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION '% is append-only', TG_TABLE_NAME
            USING ERRCODE = '23514';
        END;
        $$;
        """
    )
    for table in ("artifacts", "audit_events"):
        op.execute(
            f"CREATE TRIGGER trg_{table}_no_mutation "
            f"BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION reject_append_only_mutation()"
        )
        op.execute(
            f"CREATE TRIGGER trg_{table}_no_truncate "
            f"BEFORE TRUNCATE ON {table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION reject_append_only_mutation()"
        )


def downgrade() -> None:
    op.execute("DROP FUNCTION reject_append_only_mutation() CASCADE")
    op.drop_table("artifact_lineage")
    op.drop_index("ix_approval_workflow_status", table_name="approvals")
    op.drop_table("approvals")
    op.drop_index("ix_decision_workflow_created", table_name="decisions")
    op.drop_table("decisions")
    op.drop_table("audit_events")
    op.drop_index("ix_artifact_workflow_name", table_name="artifacts")
    op.drop_table("artifacts")
    op.drop_index("ix_stage_workflow_status", table_name="stage_runs")
    op.drop_table("stage_runs")
    op.drop_table("workflow_runs")
