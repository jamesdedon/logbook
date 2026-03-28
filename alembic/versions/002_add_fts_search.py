"""Add FTS5 full-text search

Revision ID: 002
Revises: 001
Create Date: 2026-03-28
"""
from typing import Sequence, Union

from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # FTS5 virtual table storing its own content (no content= option).
    # Kept in sync via triggers.
    op.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(
            entity_type,
            entity_id,
            title,
            body,
            tokenize='porter unicode61'
        )
    """)

    # Populate from existing data
    op.execute("""
        INSERT INTO search_index(entity_type, entity_id, title, body)
        SELECT 'project', id, name, description FROM projects
    """)
    op.execute("""
        INSERT INTO search_index(entity_type, entity_id, title, body)
        SELECT 'goal', id, title, description FROM goals
    """)
    op.execute("""
        INSERT INTO search_index(entity_type, entity_id, title, body)
        SELECT 'task', id, title, description FROM tasks
    """)
    op.execute("""
        INSERT INTO search_index(entity_type, entity_id, title, body)
        SELECT 'work_log_entry', id, description, COALESCE(metadata, '') FROM work_log_entries
    """)

    # --- Triggers to keep FTS in sync ---

    # Projects
    op.execute("""
        CREATE TRIGGER search_projects_insert AFTER INSERT ON projects BEGIN
            INSERT INTO search_index(entity_type, entity_id, title, body)
            VALUES ('project', NEW.id, NEW.name, NEW.description);
        END
    """)
    op.execute("""
        CREATE TRIGGER search_projects_update AFTER UPDATE ON projects BEGIN
            DELETE FROM search_index WHERE entity_type = 'project' AND entity_id = OLD.id;
            INSERT INTO search_index(entity_type, entity_id, title, body)
            VALUES ('project', NEW.id, NEW.name, NEW.description);
        END
    """)
    op.execute("""
        CREATE TRIGGER search_projects_delete AFTER DELETE ON projects BEGIN
            DELETE FROM search_index WHERE entity_type = 'project' AND entity_id = OLD.id;
        END
    """)

    # Goals
    op.execute("""
        CREATE TRIGGER search_goals_insert AFTER INSERT ON goals BEGIN
            INSERT INTO search_index(entity_type, entity_id, title, body)
            VALUES ('goal', NEW.id, NEW.title, NEW.description);
        END
    """)
    op.execute("""
        CREATE TRIGGER search_goals_update AFTER UPDATE ON goals BEGIN
            DELETE FROM search_index WHERE entity_type = 'goal' AND entity_id = OLD.id;
            INSERT INTO search_index(entity_type, entity_id, title, body)
            VALUES ('goal', NEW.id, NEW.title, NEW.description);
        END
    """)
    op.execute("""
        CREATE TRIGGER search_goals_delete AFTER DELETE ON goals BEGIN
            DELETE FROM search_index WHERE entity_type = 'goal' AND entity_id = OLD.id;
        END
    """)

    # Tasks
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
    op.execute("""
        CREATE TRIGGER search_tasks_delete AFTER DELETE ON tasks BEGIN
            DELETE FROM search_index WHERE entity_type = 'task' AND entity_id = OLD.id;
        END
    """)

    # Work log entries
    op.execute("""
        CREATE TRIGGER search_worklog_insert AFTER INSERT ON work_log_entries BEGIN
            INSERT INTO search_index(entity_type, entity_id, title, body)
            VALUES ('work_log_entry', NEW.id, NEW.description, COALESCE(NEW.metadata, ''));
        END
    """)
    op.execute("""
        CREATE TRIGGER search_worklog_update AFTER UPDATE ON work_log_entries BEGIN
            DELETE FROM search_index WHERE entity_type = 'work_log_entry' AND entity_id = OLD.id;
            INSERT INTO search_index(entity_type, entity_id, title, body)
            VALUES ('work_log_entry', NEW.id, NEW.description, COALESCE(NEW.metadata, ''));
        END
    """)
    op.execute("""
        CREATE TRIGGER search_worklog_delete AFTER DELETE ON work_log_entries BEGIN
            DELETE FROM search_index WHERE entity_type = 'work_log_entry' AND entity_id = OLD.id;
        END
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS search_worklog_delete")
    op.execute("DROP TRIGGER IF EXISTS search_worklog_update")
    op.execute("DROP TRIGGER IF EXISTS search_worklog_insert")
    op.execute("DROP TRIGGER IF EXISTS search_tasks_delete")
    op.execute("DROP TRIGGER IF EXISTS search_tasks_update")
    op.execute("DROP TRIGGER IF EXISTS search_tasks_insert")
    op.execute("DROP TRIGGER IF EXISTS search_goals_delete")
    op.execute("DROP TRIGGER IF EXISTS search_goals_update")
    op.execute("DROP TRIGGER IF EXISTS search_goals_insert")
    op.execute("DROP TRIGGER IF EXISTS search_projects_delete")
    op.execute("DROP TRIGGER IF EXISTS search_projects_update")
    op.execute("DROP TRIGGER IF EXISTS search_projects_insert")
    op.execute("DROP TABLE IF EXISTS search_index")
