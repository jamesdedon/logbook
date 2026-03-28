"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("status", sa.String(), server_default="active"),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint("status IN ('active', 'archived')", name="ck_project_status"),
    )

    op.create_table(
        "goals",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("status", sa.String(), server_default="active"),
        sa.Column("target_date", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint("status IN ('active', 'completed', 'abandoned')", name="ck_goal_status"),
    )

    op.create_table(
        "tasks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("goal_id", sa.String(), sa.ForeignKey("goals.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("status", sa.String(), server_default="todo"),
        sa.Column("priority", sa.String(), server_default="medium"),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.Column("completed_at", sa.String(), nullable=True),
        sa.CheckConstraint("status IN ('todo', 'in_progress', 'done', 'cancelled')", name="ck_task_status"),
        sa.CheckConstraint("priority IN ('low', 'medium', 'high', 'critical')", name="ck_task_priority"),
    )
    op.create_index("idx_tasks_project", "tasks", ["project_id"])
    op.create_index("idx_tasks_goal", "tasks", ["goal_id"])
    op.create_index("idx_tasks_status", "tasks", ["status"])
    op.create_index("idx_tasks_priority", "tasks", ["priority"])

    op.create_table(
        "task_dependencies",
        sa.Column("blocker_id", sa.String(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("blocked_id", sa.String(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.CheckConstraint("blocker_id != blocked_id", name="ck_no_self_dep"),
    )

    op.create_table(
        "work_log_entries",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("task_id", sa.String(), sa.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("metadata", sa.Text(), server_default="{}"),
        sa.Column("created_at", sa.String(), nullable=False),
    )
    op.create_index("idx_worklog_project", "work_log_entries", ["project_id"])
    op.create_index("idx_worklog_task", "work_log_entries", ["task_id"])
    op.create_index("idx_worklog_created", "work_log_entries", ["created_at"])

    op.create_table(
        "tags",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=False),
        sa.Column("tag", sa.String(), nullable=False),
        sa.CheckConstraint(
            "entity_type IN ('project', 'goal', 'task', 'work_log_entry')",
            name="ck_tag_entity_type",
        ),
        sa.UniqueConstraint("entity_type", "entity_id", "tag", name="uq_tag"),
    )
    op.create_index("idx_tags_entity", "tags", ["entity_type", "entity_id"])
    op.create_index("idx_tags_tag", "tags", ["tag"])


def downgrade() -> None:
    op.drop_table("tags")
    op.drop_table("work_log_entries")
    op.drop_table("task_dependencies")
    op.drop_table("tasks")
    op.drop_table("goals")
    op.drop_table("projects")
