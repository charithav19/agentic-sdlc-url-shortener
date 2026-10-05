"""Add exclusive fenced stage claims.

Revision ID: 0004_stage_claims
Revises: 0003_approval_checkpoints
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_stage_claims"
down_revision: str | None = "0003_approval_checkpoints"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("stage_runs", sa.Column("claim_owner", sa.String(length=128), nullable=True))
    op.create_index(
        "uq_stage_active_claim",
        "stage_runs",
        ["workflow_id", "generation", "stage_name"],
        unique=True,
        postgresql_where=sa.text("lease_token IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_stage_active_claim", table_name="stage_runs")
    op.drop_column("stage_runs", "claim_owner")
