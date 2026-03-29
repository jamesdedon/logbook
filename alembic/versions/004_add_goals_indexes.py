"""Add missing indexes on goals table

Revision ID: 004
Revises: 003
Create Date: 2026-03-28
"""
from typing import Sequence, Union

from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("idx_goals_project", "goals", ["project_id"])
    op.create_index("idx_goals_status", "goals", ["status"])


def downgrade() -> None:
    op.drop_index("idx_goals_status")
    op.drop_index("idx_goals_project")
