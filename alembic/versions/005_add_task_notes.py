"""Add notes column to tasks

Revision ID: 005
Revises: 004
Create Date: 2026-04-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("notes", sa.Text(), server_default="", nullable=False))

    # Update FTS triggers to include notes in the search body
    op.execute("DROP TRIGGER IF EXISTS search_tasks_insert")
    op.execute("DROP TRIGGER IF EXISTS search_tasks_update")

    op.execute("""
        CREATE TRIGGER search_tasks_insert AFTER INSERT ON tasks BEGIN
            INSERT INTO search_index(entity_type, entity_id, title, body)
            VALUES ('task', NEW.id, NEW.title, NEW.description || ' ' || NEW.notes);
        END
    """)
    op.execute("""
        CREATE TRIGGER search_tasks_update AFTER UPDATE ON tasks BEGIN
            DELETE FROM search_index WHERE entity_type = 'task' AND entity_id = OLD.id;
            INSERT INTO search_index(entity_type, entity_id, title, body)
            VALUES ('task', NEW.id, NEW.title, NEW.description || ' ' || NEW.notes);
        END
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS search_tasks_insert")
    op.execute("DROP TRIGGER IF EXISTS search_tasks_update")

    op.execute("""
        CREATE TRIGGER search_tasks_insert AFTER INSERT ON tasks BEGIN
            INSERT INTO search_index(entity_type, entity_id, title, body)
            VALUES ('task', NEW.id, NEW.title, NEW.description);
        END
    """)
    op.execute("""
        CREATE TRIGGER search_tasks_update AFTER UPDATE ON tasks BEGIN
            DELETE FROM search_index WHERE entity_type = 'task' AND entity_id = OLD.id;
            INSERT INTO search_index(entity_type, entity_id, title, body)
            VALUES ('task', NEW.id, NEW.title, NEW.description);
        END
    """)

    op.drop_column("tasks", "notes")
