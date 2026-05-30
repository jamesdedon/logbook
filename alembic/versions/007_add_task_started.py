"""Add started_at column to tasks

`started_at` records when a task first moved to in_progress — the moment you began
the work. Set automatically on the todo -> in_progress transition (mirrors how
completed_at is set on -> done). Nullable: unset until a task is started.

Revision ID: 007
Revises: 006
Create Date: 2026-05-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("started_at", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "started_at")
