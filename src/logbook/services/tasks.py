from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from logbook.models import Tag, Task, TaskDependency, WorkLogEntry


async def create_task(
    db: AsyncSession,
    project_id: str,
    title: str,
    description: str = "",
    priority: str = "medium",
    goal_id: str | None = None,
    tags: list[str] | None = None,
    blocked_by: list[str] | None = None,
) -> Task:
    task = Task(
        project_id=project_id,
        title=title,
        description=description,
        priority=priority,
        goal_id=goal_id,
    )
    db.add(task)
    await db.flush()
    if tags:
        for t in tags:
            db.add(Tag(entity_type="task", entity_id=task.id, tag=t))
    if blocked_by:
        for blocker_id in blocked_by:
            db.add(TaskDependency(blocker_id=blocker_id, blocked_id=task.id))
    await db.commit()
    await db.refresh(task)
    return task


async def list_tasks(
    db: AsyncSession,
    project_id: str | None = None,
    goal_id: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    blocked: bool | None = None,
    tag: str | None = None,
    q: str | None = None,
    sort: str = "created_at_desc",
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Task], int]:
    stmt = select(Task)
    count_stmt = select(func.count()).select_from(Task)

    filters = []
    if project_id:
        filters.append(Task.project_id == project_id)
    if goal_id:
        filters.append(Task.goal_id == goal_id)
    if status:
        statuses = [s.strip() for s in status.split(",")]
        filters.append(Task.status.in_(statuses))
    if priority:
        priorities = [p.strip() for p in priority.split(",")]
        filters.append(Task.priority.in_(priorities))
    if q:
        pattern = f"%{q}%"
        filters.append(or_(Task.title.ilike(pattern), Task.description.ilike(pattern)))
    if tag:
        tag_subq = select(Tag.entity_id).where(Tag.entity_type == "task", Tag.tag == tag)
        filters.append(Task.id.in_(tag_subq))

    for f in filters:
        stmt = stmt.where(f)
        count_stmt = count_stmt.where(f)

    if blocked is not None:
        blocked_subq = (
            select(TaskDependency.blocked_id)
            .join(Task, Task.id == TaskDependency.blocker_id)
            .where(Task.status != "done")
            .distinct()
        )
        if blocked:
            stmt = stmt.where(Task.id.in_(blocked_subq))
            count_stmt = count_stmt.where(Task.id.in_(blocked_subq))
        else:
            stmt = stmt.where(Task.id.notin_(blocked_subq))
            count_stmt = count_stmt.where(Task.id.notin_(blocked_subq))

    # Sorting
    sort_map = {
        "created_at_desc": Task.created_at.desc(),
        "created_at_asc": Task.created_at.asc(),
        "updated_at_desc": Task.updated_at.desc(),
        "priority_desc": Task.priority.desc(),
    }
    stmt = stmt.order_by(sort_map.get(sort, Task.created_at.desc()))
    stmt = stmt.limit(limit).offset(offset)

    total = await db.scalar(count_stmt) or 0
    result = await db.execute(stmt)
    return list(result.scalars().all()), total


async def get_task(db: AsyncSession, task_id: str) -> Task | None:
    stmt = (
        select(Task)
        .where(Task.id == task_id)
        .options(selectinload(Task.blocked_by), selectinload(Task.blocks))
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_task_blockers(db: AsyncSession, task_id: str) -> list[Task]:
    stmt = (
        select(Task)
        .join(TaskDependency, TaskDependency.blocker_id == Task.id)
        .where(TaskDependency.blocked_id == task_id)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_task_blockees(db: AsyncSession, task_id: str) -> list[Task]:
    stmt = (
        select(Task)
        .join(TaskDependency, TaskDependency.blocked_id == Task.id)
        .where(TaskDependency.blocker_id == task_id)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def is_task_blocked(db: AsyncSession, task_id: str) -> bool:
    stmt = (
        select(func.count())
        .select_from(TaskDependency)
        .join(Task, Task.id == TaskDependency.blocker_id)
        .where(TaskDependency.blocked_id == task_id, Task.status != "done")
    )
    count = await db.scalar(stmt)
    return (count or 0) > 0


async def get_recent_log_entries(db: AsyncSession, task_id: str, limit: int = 5) -> list[WorkLogEntry]:
    stmt = (
        select(WorkLogEntry)
        .where(WorkLogEntry.task_id == task_id)
        .order_by(WorkLogEntry.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_task(db: AsyncSession, task_id: str, **kwargs) -> Task | None:
    task = await db.get(Task, task_id)
    if not task:
        return None
    for key, value in kwargs.items():
        if value is not None:
            setattr(task, key, value)
    if kwargs.get("status") == "done" and not task.completed_at:
        task.completed_at = datetime.now(timezone.utc).isoformat()
    await db.commit()
    await db.refresh(task)
    return task


async def delete_task(db: AsyncSession, task_id: str) -> bool:
    task = await db.get(Task, task_id)
    if not task:
        return False
    await db.delete(task)
    await db.commit()
    return True


async def add_dependency(db: AsyncSession, task_id: str, blocker_id: str) -> TaskDependency:
    dep = TaskDependency(blocker_id=blocker_id, blocked_id=task_id)
    db.add(dep)
    await db.commit()
    return dep


async def remove_dependency(db: AsyncSession, task_id: str, blocker_id: str) -> bool:
    stmt = select(TaskDependency).where(
        TaskDependency.blocked_id == task_id, TaskDependency.blocker_id == blocker_id
    )
    result = await db.execute(stmt)
    dep = result.scalar_one_or_none()
    if not dep:
        return False
    await db.delete(dep)
    await db.commit()
    return True
