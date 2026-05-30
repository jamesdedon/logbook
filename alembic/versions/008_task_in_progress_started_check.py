"""Enforce: an in_progress task must have a started_at

Ties task status to the started_at stamp at the storage layer — a task cannot be
in_progress without a start date. SQLite can't ALTER ADD CONSTRAINT, so this uses
alembic's batch mode to rebuild the table. Safe to add: there are no existing
in_progress rows missing started_at (the service layer already stamps them).

Revision ID: 008
Revises: 007
Create Date: 2026-05-30
"""
from typing import Sequence, Union

from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.create_check_constraint(
            "ck_task_in_progress_started",
            "status != 'in_progress' OR started_at IS NOT NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_constraint("ck_task_in_progress_started", type_="check")
