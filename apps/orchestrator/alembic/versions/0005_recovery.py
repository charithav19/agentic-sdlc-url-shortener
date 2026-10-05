"""Persist classified recovery and fallback provenance.

Revision ID: 0005_recovery
Revises: 0004_stage_claims
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_recovery"
down_revision: str | None = "0004_stage_claims"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("workflow_runs", sa.Column("recommended_human_action", sa.Text()))
    op.add_column("stage_runs", sa.Column("failure_code", sa.String(length=64)))
    op.add_column("stage_runs", sa.Column("recommended_action", sa.Text()))
    op.add_column(
        "stage_runs",
        sa.Column(
            "execution_mode",
            sa.String(length=16),
            nullable=False,
            server_default="PRIMARY",
        ),
    )
    op.add_column("stage_runs", sa.Column("fallback_source_stage_run_id", sa.Uuid()))
    op.create_foreign_key(
        "fk_stage_fallback_source",
        "stage_runs",
        "stage_runs",
        ["fallback_source_stage_run_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_stage_execution_mode",
        "stage_runs",
        "execution_mode IN ('PRIMARY', 'FALLBACK')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_stage_execution_mode", "stage_runs", type_="check")
    op.drop_constraint("fk_stage_fallback_source", "stage_runs", type_="foreignkey")
    op.drop_column("stage_runs", "fallback_source_stage_run_id")
    op.drop_column("stage_runs", "execution_mode")
    op.drop_column("stage_runs", "recommended_action")
    op.drop_column("stage_runs", "failure_code")
    op.drop_column("workflow_runs", "recommended_human_action")
