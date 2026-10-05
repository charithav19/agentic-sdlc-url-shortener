"""Constrain exact-version approval checkpoints.

Revision ID: 0003_approval_checkpoints
Revises: 0002_workflow_foundation
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_approval_checkpoints"
down_revision: str | None = "0002_workflow_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_approval_type",
        "approvals",
        "approval_type IN "
        "('ARCHITECTURE', 'HIGH_IMPACT_CHANGE', 'ASSUMPTION', 'RELEASE')",
    )
    op.create_check_constraint(
        "ck_approval_artifact_version", "approvals", "artifact_version > 0"
    )
    op.create_index(
        "uq_approval_pending_exact",
        "approvals",
        ["workflow_id", "approval_type", "artifact_id", "artifact_version"],
        unique=True,
        postgresql_where=sa.text("status = 'PENDING'"),
    )


def downgrade() -> None:
    op.drop_index("uq_approval_pending_exact", table_name="approvals")
    op.drop_constraint("ck_approval_artifact_version", "approvals", type_="check")
    op.drop_constraint("ck_approval_type", "approvals", type_="check")
