"""Persist append-only deterministic policy decisions.

Revision ID: 0008_policy_events
Revises: 0007_lineage_indexes
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0008_policy_events"
down_revision: str | None = "0007_lineage_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "policy_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("stage_run_id", sa.Uuid(), nullable=True),
        sa.Column("policy_set_version", sa.String(length=32), nullable=False),
        sa.Column("policy_set_hash", sa.String(length=64), nullable=False),
        sa.Column("rule_id", sa.String(length=128), nullable=False),
        sa.Column("rule_version", sa.String(length=32), nullable=False),
        sa.Column("result", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("actor_type", sa.String(length=16), nullable=False),
        sa.Column("actor_id", sa.String(length=128), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("blocking", sa.Boolean(), nullable=False),
        sa.Column("artifact_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "result IN ('ALLOW', 'DENY', 'REQUIRE_APPROVAL')",
            name="ck_policy_event_result",
        ),
        sa.CheckConstraint(
            "actor_type IN ('SYSTEM', 'AGENT', 'HUMAN')",
            name="ck_policy_event_actor_type",
        ),
        sa.CheckConstraint(
            "policy_set_hash ~ '^[0-9a-f]{64}$'",
            name="ck_policy_event_set_hash",
        ),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflow_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["stage_run_id"], ["stage_runs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_policy_event_workflow_created",
        "policy_events",
        ["workflow_id", "created_at"],
    )
    op.create_index(
        "ix_policy_event_workflow_result",
        "policy_events",
        ["workflow_id", "result"],
    )
    op.execute(
        "CREATE TRIGGER trg_policy_events_no_mutation "
        "BEFORE UPDATE OR DELETE ON policy_events "
        "FOR EACH ROW EXECUTE FUNCTION reject_append_only_mutation()"
    )
    op.execute(
        "CREATE TRIGGER trg_policy_events_no_truncate "
        "BEFORE TRUNCATE ON policy_events "
        "FOR EACH STATEMENT EXECUTE FUNCTION reject_append_only_mutation()"
    )


def downgrade() -> None:
    op.drop_index("ix_policy_event_workflow_result", table_name="policy_events")
    op.drop_index("ix_policy_event_workflow_created", table_name="policy_events")
    op.drop_table("policy_events")
