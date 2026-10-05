"""Constrain and index typed artifact lineage.

Revision ID: 0007_lineage_indexes
Revises: 0006_compensations
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007_lineage_indexes"
down_revision: str | None = "0006_compensations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Phase 6 used REVISES in its version fixture before the typed vocabulary
    # was established. Its direction matches SUPERSEDES (older -> newer).
    op.execute(
        "UPDATE artifact_lineage SET relationship = 'SUPERSEDES' WHERE relationship = 'REVISES'"
    )
    op.create_check_constraint(
        "ck_lineage_relationship",
        "artifact_lineage",
        "relationship IN ('DERIVED_FROM', 'IMPLEMENTS', 'VALIDATES', 'DOCUMENTS', 'SUPERSEDES')",
    )
    op.create_index(
        "ix_lineage_workflow_parent",
        "artifact_lineage",
        ["workflow_id", "parent_artifact_id"],
    )
    op.create_index(
        "ix_lineage_workflow_child",
        "artifact_lineage",
        ["workflow_id", "child_artifact_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_lineage_workflow_child", table_name="artifact_lineage")
    op.drop_index("ix_lineage_workflow_parent", table_name="artifact_lineage")
    op.drop_constraint("ck_lineage_relationship", "artifact_lineage", type_="check")
