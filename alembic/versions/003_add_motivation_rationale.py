"""Add motivation/rationale fields and update FTS triggers

Revision ID: 003
Revises: 002
Create Date: 2026-03-28
"""
from typing import Sequence, Union

from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add motivation column to projects and goals
    op.execute("ALTER TABLE projects ADD COLUMN motivation TEXT DEFAULT ''")
    op.execute("ALTER TABLE goals ADD COLUMN motivation TEXT DEFAULT ''")
    # Add rationale column to tasks
    op.execute("ALTER TABLE tasks ADD COLUMN rationale TEXT DEFAULT ''")

    # Update FTS triggers to include motivation/rationale in search body

    # Projects: drop old triggers, create new ones that include motivation
    op.execute("DROP TRIGGER IF EXISTS search_projects_insert")
    op.execute("DROP TRIGGER IF EXISTS search_projects_update")
    op.execute("""
        CREATE TRIGGER search_projects_insert AFTER INSERT ON projects BEGIN
            INSERT INTO search_index(entity_type, entity_id, title, body)
            VALUES ('project', NEW.id, NEW.name, NEW.description || ' ' || COALESCE(NEW.motivation, ''));
        END
    """)
    op.execute("""
        CREATE TRIGGER search_projects_update AFTER UPDATE ON projects BEGIN
            DELETE FROM search_index WHERE entity_type = 'project' AND entity_id = OLD.id;
            INSERT INTO search_index(entity_type, entity_id, title, body)
            VALUES ('project', NEW.id, NEW.name, NEW.description || ' ' || COALESCE(NEW.motivation, ''));
        END
    """)

    # Goals: drop old triggers, create new ones that include motivation
    op.execute("DROP TRIGGER IF EXISTS search_goals_insert")
    op.execute("DROP TRIGGER IF EXISTS search_goals_update")
    op.execute("""
        CREATE TRIGGER search_goals_insert AFTER INSERT ON goals BEGIN
            INSERT INTO search_index(entity_type, entity_id, title, body)
            VALUES ('goal', NEW.id, NEW.title, NEW.description || ' ' || COALESCE(NEW.motivation, ''));
        END
    """)
    op.execute("""
        CREATE TRIGGER search_goals_update AFTER UPDATE ON goals BEGIN
            DELETE FROM search_index WHERE entity_type = 'goal' AND entity_id = OLD.id;
            INSERT INTO search_index(entity_type, entity_id, title, body)
            VALUES ('goal', NEW.id, NEW.title, NEW.description || ' ' || COALESCE(NEW.motivation, ''));
        END
    """)

    # Tasks: drop old triggers, create new ones that include rationale
    op.execute("DROP TRIGGER IF EXISTS search_tasks_insert")
    op.execute("DROP TRIGGER IF EXISTS search_tasks_update")
    op.execute("""
        CREATE TRIGGER search_tasks_insert AFTER INSERT ON tasks BEGIN
            INSERT INTO search_index(entity_type, entity_id, title, body)
            VALUES ('task', NEW.id, NEW.title, NEW.description || ' ' || COALESCE(NEW.rationale, ''));
        END
    """)
    op.execute("""
        CREATE TRIGGER search_tasks_update AFTER UPDATE ON tasks BEGIN
            DELETE FROM search_index WHERE entity_type = 'task' AND entity_id = OLD.id;
            INSERT INTO search_index(entity_type, entity_id, title, body)
            VALUES ('task', NEW.id, NEW.title, NEW.description || ' ' || COALESCE(NEW.rationale, ''));
        END
    """)

    # Re-index existing data to pick up any motivation/rationale already set
    op.execute("DELETE FROM search_index WHERE entity_type IN ('project', 'goal', 'task')")
    op.execute("""
        INSERT INTO search_index(entity_type, entity_id, title, body)
        SELECT 'project', id, name, description || ' ' || COALESCE(motivation, '') FROM projects
    """)
    op.execute("""
        INSERT INTO search_index(entity_type, entity_id, title, body)
        SELECT 'goal', id, title, description || ' ' || COALESCE(motivation, '') FROM goals
    """)
    op.execute("""
        INSERT INTO search_index(entity_type, entity_id, title, body)
        SELECT 'task', id, title, description || ' ' || COALESCE(rationale, '') FROM tasks
    """)


def downgrade() -> None:
    # Restore original triggers (without motivation/rationale)
    op.execute("DROP TRIGGER IF EXISTS search_projects_insert")
    op.execute("DROP TRIGGER IF EXISTS search_projects_update")
    op.execute("DROP TRIGGER IF EXISTS search_goals_insert")
    op.execute("DROP TRIGGER IF EXISTS search_goals_update")
    op.execute("DROP TRIGGER IF EXISTS search_tasks_insert")
    op.execute("DROP TRIGGER IF EXISTS search_tasks_update")

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

    # Note: SQLite doesn't support DROP COLUMN, so we leave the columns in place
