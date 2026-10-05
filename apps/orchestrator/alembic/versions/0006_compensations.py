"""Add semantic candidate lifecycle and compensation records.

Revision ID: 0006_compensations
Revises: 0005_recovery
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_compensations"
down_revision: str | None = "0005_recovery"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "artifact_lifecycle",
        sa.Column("artifact_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('CANDIDATE', 'APPROVED', 'ROLLED_BACK', 'STALE')",
            name="ck_artifact_lifecycle_status",
        ),
        sa.CheckConstraint("version > 0", name="ck_artifact_lifecycle_version"),
        sa.ForeignKeyConstraint(
            ["workflow_id", "artifact_id"],
            ["artifacts.workflow_id", "artifacts.id"],
            name="fk_artifact_lifecycle_exact_artifact",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("artifact_id"),
    )
    op.create_index(
        "ix_artifact_lifecycle_workflow_status",
        "artifact_lifecycle",
        ["workflow_id", "status"],
    )
    op.create_table(
        "candidate_references",
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("logical_name", sa.String(length=128), nullable=False),
        sa.Column("active_artifact_id", sa.Uuid(), nullable=True),
        sa.Column("approved_artifact_id", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("version > 0", name="ck_candidate_ref_version"),
        sa.ForeignKeyConstraint(
            ["workflow_id", "active_artifact_id"],
            ["artifacts.workflow_id", "artifacts.id"],
            name="fk_candidate_ref_active",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id", "approved_artifact_id"],
            ["artifacts.workflow_id", "artifacts.id"],
            name="fk_candidate_ref_approved",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflow_runs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("workflow_id", "logical_name"),
    )
    op.create_table(
        "compensations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_artifact_id", sa.Uuid(), nullable=False),
        sa.Column("cause_stage_run_id", sa.Uuid(), nullable=False),
        sa.Column("previous_approved_artifact_id", sa.Uuid(), nullable=True),
        sa.Column("restored_artifact_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('STARTED', 'COMPLETED', 'FAILED')", name="ck_compensation_status"
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id", "candidate_artifact_id"],
            ["artifacts.workflow_id", "artifacts.id"],
            name="fk_compensation_candidate",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id", "previous_approved_artifact_id"],
            ["artifacts.workflow_id", "artifacts.id"],
            name="fk_compensation_previous_approved",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id", "restored_artifact_id"],
            ["artifacts.workflow_id", "artifacts.id"],
            name="fk_compensation_restored",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["cause_stage_run_id"], ["stage_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflow_runs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workflow_id",
            "candidate_artifact_id",
            "cause_stage_run_id",
            name="uq_compensation_cause",
        ),
    )
    op.create_index("ix_compensation_workflow_status", "compensations", ["workflow_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_compensation_workflow_status", table_name="compensations")
    op.drop_table("compensations")
    op.drop_table("candidate_references")
    op.drop_index("ix_artifact_lifecycle_workflow_status", table_name="artifact_lifecycle")
    op.drop_table("artifact_lifecycle")
