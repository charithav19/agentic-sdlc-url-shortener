"""Establish the orchestrator migration baseline.

Revision ID: 0001_database_baseline
Revises:
"""

from collections.abc import Sequence

revision: str = "0001_database_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Workflow tables begin in Phase 6."""


def downgrade() -> None:
    """Return to an unmigrated database."""
