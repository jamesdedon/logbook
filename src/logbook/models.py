from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from ulid import ULID


def _ulid() -> str:
    return str(ULID())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_ulid)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String, default="active")
    created_at: Mapped[str] = mapped_column(String, default=_now)
    updated_at: Mapped[str] = mapped_column(String, default=_now, onupdate=_now)

    goals: Mapped[list["Goal"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    tasks: Mapped[list["Task"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    log_entries: Mapped[list["WorkLogEntry"]] = relationship(back_populates="project")

    __table_args__ = (
        CheckConstraint("status IN ('active', 'archived')", name="ck_project_status"),
    )


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_ulid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String, default="active")
    target_date: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, default=_now)
    updated_at: Mapped[str] = mapped_column(String, default=_now, onupdate=_now)

    project: Mapped["Project"] = relationship(back_populates="goals")
    tasks: Mapped[list["Task"]] = relationship(back_populates="goal")

    __table_args__ = (
        CheckConstraint("status IN ('active', 'completed', 'abandoned')", name="ck_goal_status"),
    )


class TaskDependency(Base):
    __tablename__ = "task_dependencies"

    blocker_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True)
    blocked_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[str] = mapped_column(String, default=_now)

    __table_args__ = (
        CheckConstraint("blocker_id != blocked_id", name="ck_no_self_dep"),
    )


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_ulid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    goal_id: Mapped[str | None] = mapped_column(ForeignKey("goals.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String, default="todo")
    priority: Mapped[str] = mapped_column(String, default="medium")
    created_at: Mapped[str] = mapped_column(String, default=_now)
    updated_at: Mapped[str] = mapped_column(String, default=_now, onupdate=_now)
    completed_at: Mapped[str | None] = mapped_column(String, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="tasks")
    goal: Mapped["Goal | None"] = relationship(back_populates="tasks")

    blocked_by: Mapped[list["TaskDependency"]] = relationship(
        foreign_keys=[TaskDependency.blocked_id],
        cascade="all, delete-orphan",
    )
    blocks: Mapped[list["TaskDependency"]] = relationship(
        foreign_keys=[TaskDependency.blocker_id],
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint("status IN ('todo', 'in_progress', 'done', 'cancelled')", name="ck_task_status"),
        CheckConstraint("priority IN ('low', 'medium', 'high', 'critical')", name="ck_task_priority"),
        Index("idx_tasks_project", "project_id"),
        Index("idx_tasks_goal", "goal_id"),
        Index("idx_tasks_status", "status"),
        Index("idx_tasks_priority", "priority"),
    )


class WorkLogEntry(Base):
    __tablename__ = "work_log_entries"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_ulid)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[str] = mapped_column("metadata", Text, default="{}")
    created_at: Mapped[str] = mapped_column(String, default=_now)

    project: Mapped["Project | None"] = relationship(back_populates="log_entries")

    __table_args__ = (
        Index("idx_worklog_project", "project_id"),
        Index("idx_worklog_task", "task_id"),
        Index("idx_worklog_created", "created_at"),
    )


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_ulid)
    entity_type: Mapped[str] = mapped_column(String, nullable=False)
    entity_id: Mapped[str] = mapped_column(String, nullable=False)
    tag: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "entity_type IN ('project', 'goal', 'task', 'work_log_entry')",
            name="ck_tag_entity_type",
        ),
        UniqueConstraint("entity_type", "entity_id", "tag", name="uq_tag"),
        Index("idx_tags_entity", "entity_type", "entity_id"),
        Index("idx_tags_tag", "tag"),
    )
