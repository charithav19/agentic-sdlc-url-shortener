"""Add indexes for durable orchestration metric reporting.

Revision ID: 0009_observability_indexes
Revises: 0008_policy_events
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0009_observability_indexes"
down_revision: str | None = "0008_policy_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_workflow_status_created_at", "workflow_runs", ["status", "created_at"])
    op.create_index("ix_stage_started_completed", "stage_runs", ["started_at", "completed_at"])
    op.create_index("ix_audit_event_type_occurred", "audit_events", ["event_type", "occurred_at"])
    op.create_index("ix_audit_after_state_occurred", "audit_events", ["after_state", "occurred_at"])
    op.create_index("ix_approval_status_created_at", "approvals", ["status", "created_at"])
    op.create_index("ix_compensation_status_completed", "compensations", ["status", "completed_at"])


def downgrade() -> None:
    op.drop_index("ix_compensation_status_completed", table_name="compensations")
    op.drop_index("ix_approval_status_created_at", table_name="approvals")
    op.drop_index("ix_audit_after_state_occurred", table_name="audit_events")
    op.drop_index("ix_audit_event_type_occurred", table_name="audit_events")
    op.drop_index("ix_stage_started_completed", table_name="stage_runs")
    op.drop_index("ix_workflow_status_created_at", table_name="workflow_runs")
