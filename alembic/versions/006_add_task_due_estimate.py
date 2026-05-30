"""Add due and estimate_minutes columns to tasks

`due` makes a task a scheduled commitment — it's what the temporal "next" queue
sorts on (next = dated only, by due ascending). `estimate_minutes` records task
size so a calendar planner can fit tasks into free time. Both are nullable: an
undated task is a first-class backlog item ranked by priority, never penalized.

Revision ID: 006
Revises: 005
Create Date: 2026-05-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("due", sa.String(), nullable=True))
    op.add_column("tasks", sa.Column("estimate_minutes", sa.Integer(), nullable=True))
    op.create_index("idx_tasks_due", "tasks", ["due"])


def downgrade() -> None:
    op.drop_index("idx_tasks_due", table_name="tasks")
    op.drop_column("tasks", "estimate_minutes")
    op.drop_column("tasks", "due")
