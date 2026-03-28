from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from logbook.config import settings
from logbook.models import Goal, Project, Task, TaskDependency, WorkLogEntry


async def get_summary(db: AsyncSession) -> dict:
    # Active projects with counts
    projects_result = await db.execute(select(Project).where(Project.status == "active"))
    projects = list(projects_result.scalars().all())

    active_projects = []
    for p in projects:
        goals_count = await db.scalar(
            select(func.count()).where(Goal.project_id == p.id, Goal.status == "active")
        )
        task_counts = {}
        for status in ("todo", "in_progress", "done", "cancelled"):
            count = await db.scalar(
                select(func.count()).where(Task.project_id == p.id, Task.status == status)
            )
            task_counts[status] = count or 0

        blocked_count = await db.scalar(
            select(func.count())
            .select_from(Task)
            .where(
                Task.project_id == p.id,
                Task.status.in_(["todo", "in_progress"]),
                Task.id.in_(
                    select(TaskDependency.blocked_id)
                    .join(Task, Task.id == TaskDependency.blocker_id)
                    .where(Task.status != "done")
                ),
            )
        )

        active_projects.append({
            "id": p.id,
            "name": p.name,
            "goals_active": goals_count or 0,
            "tasks_summary": task_counts,
            "blocked_tasks": blocked_count or 0,
        })

    # Recent activity (last 10 entries)
    recent_result = await db.execute(
        select(WorkLogEntry).order_by(WorkLogEntry.created_at.desc()).limit(10)
    )
    recent_activity = list(recent_result.scalars().all())

    # Blocked tasks
    blocked_subq = (
        select(TaskDependency.blocked_id)
        .join(Task, Task.id == TaskDependency.blocker_id)
        .where(Task.status != "done")
        .distinct()
    )
    blocked_result = await db.execute(
        select(Task).where(Task.id.in_(blocked_subq), Task.status.in_(["todo", "in_progress"]))
    )
    blocked_tasks = list(blocked_result.scalars().all())

    # Next actions
    next_tasks = await get_next_actions(db)

    return {
        "active_projects": active_projects,
        "recent_activity": recent_activity,
        "blocked_tasks": blocked_tasks,
        "next_actions": next_tasks,
    }


async def get_today(db: AsyncSession) -> dict:
    local_now = datetime.now(settings.tz)
    today_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc).isoformat()

    log_result = await db.execute(
        select(WorkLogEntry)
        .where(WorkLogEntry.created_at >= today_start)
        .order_by(WorkLogEntry.created_at.desc())
    )
    log_entries = list(log_result.scalars().all())

    tasks_result = await db.execute(
        select(Task)
        .where(Task.completed_at >= today_start, Task.status == "done")
        .order_by(Task.completed_at.desc())
    )
    tasks_completed = list(tasks_result.scalars().all())

    return {"log_entries": log_entries, "tasks_completed": tasks_completed}


async def get_next_actions(db: AsyncSession, limit: int = 10) -> list[dict]:
    # Unblocked todo/in_progress tasks, ordered by priority then unblocks-count then age
    blocked_subq = (
        select(TaskDependency.blocked_id)
        .join(Task, Task.id == TaskDependency.blocker_id)
        .where(Task.status != "done")
        .distinct()
    )

    # Count how many tasks each task unblocks
    unblocks_count = (
        select(
            TaskDependency.blocker_id.label("task_id"),
            func.count().label("unblocks"),
        )
        .group_by(TaskDependency.blocker_id)
        .subquery()
    )

    priority_order = case(
        {"critical": 0, "high": 1, "medium": 2, "low": 3},
        value=Task.priority,
        else_=4,
    )

    stmt = (
        select(Task, func.coalesce(unblocks_count.c.unblocks, 0).label("unblocks"))
        .outerjoin(unblocks_count, unblocks_count.c.task_id == Task.id)
        .where(
            Task.status.in_(["todo", "in_progress"]),
            Task.id.notin_(blocked_subq),
        )
        .order_by(priority_order, literal_column("unblocks").desc(), Task.created_at.asc())
        .limit(limit)
    )

    result = await db.execute(stmt)
    rows = result.all()

    next_actions = []
    for row in rows:
        task = row[0]
        # Get project name
        project = await db.get(Project, task.project_id)
        next_actions.append({
            "id": task.id,
            "title": task.title,
            "priority": task.priority,
            "project_id": task.project_id,
            "project_name": project.name if project else "unknown",
        })

    return next_actions


async def get_weekly_report(db: AsyncSession, weeks_back: int = 0, project_id: str | None = None) -> dict:
    """Generate a weekly report. weeks_back=0 is the current week, 1 is last week, etc."""
    now = datetime.now(timezone.utc)
    # Find the start of the target week (Monday)
    current_monday = now - timedelta(days=now.weekday())
    week_start = (current_monday - timedelta(weeks=weeks_back)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    week_end = (week_start + timedelta(days=7)).isoformat()
    week_start_iso = week_start.isoformat()

    # Work log entries for the week
    log_stmt = (
        select(WorkLogEntry)
        .where(WorkLogEntry.created_at >= week_start_iso, WorkLogEntry.created_at < week_end)
    )
    if project_id:
        log_stmt = log_stmt.where(WorkLogEntry.project_id == project_id)
    log_result = await db.execute(log_stmt.order_by(WorkLogEntry.created_at.asc()))
    log_entries = list(log_result.scalars().all())

    # Tasks completed this week
    tasks_stmt = (
        select(Task)
        .where(Task.completed_at >= week_start_iso, Task.completed_at < week_end, Task.status == "done")
    )
    if project_id:
        tasks_stmt = tasks_stmt.where(Task.project_id == project_id)
    tasks_result = await db.execute(tasks_stmt.order_by(Task.completed_at.asc()))
    tasks_completed = list(tasks_result.scalars().all())

    # Tasks created this week
    tasks_created_stmt = (
        select(Task)
        .where(Task.created_at >= week_start_iso, Task.created_at < week_end)
    )
    if project_id:
        tasks_created_stmt = tasks_created_stmt.where(Task.project_id == project_id)
    tasks_created_result = await db.execute(tasks_created_stmt.order_by(Task.created_at.asc()))
    tasks_created = list(tasks_created_result.scalars().all())

    # Goals completed this week
    goals_stmt = (
        select(Goal)
        .where(Goal.updated_at >= week_start_iso, Goal.updated_at < week_end, Goal.status == "completed")
    )
    if project_id:
        goals_stmt = goals_stmt.where(Goal.project_id == project_id)
    goals_result = await db.execute(goals_stmt)
    goals_completed = list(goals_result.scalars().all())

    # Group log entries by day
    days: dict[str, list] = {}
    for entry in log_entries:
        day = entry.created_at[:10]
        days.setdefault(day, []).append(entry)

    # Group log entries by project
    by_project: dict[str, list] = {}
    for entry in log_entries:
        pid = entry.project_id or "unlinked"
        by_project.setdefault(pid, []).append(entry)

    # Resolve project names (from log entries + tasks)
    all_project_ids = set(by_project.keys())
    for t in tasks_completed:
        if t.project_id:
            all_project_ids.add(t.project_id)
    for t in tasks_created:
        if t.project_id:
            all_project_ids.add(t.project_id)
    all_project_ids.discard("unlinked")

    project_names = {}
    for pid in all_project_ids:
        proj = await db.get(Project, pid)
        project_names[pid] = proj.name if proj else "unknown"
    if "unlinked" in by_project:
        project_names["unlinked"] = "Unlinked"

    return {
        "week_start": week_start_iso,
        "week_end": week_end,
        "total_log_entries": len(log_entries),
        "total_tasks_completed": len(tasks_completed),
        "total_tasks_created": len(tasks_created),
        "total_goals_completed": len(goals_completed),
        "log_entries": log_entries,
        "tasks_completed": tasks_completed,
        "tasks_created": tasks_created,
        "goals_completed": goals_completed,
        "days": days,
        "by_project": by_project,
        "project_names": project_names,
    }


async def get_blocked_tasks(db: AsyncSession) -> list[dict]:
    blocked_subq = (
        select(TaskDependency.blocked_id)
        .join(Task, Task.id == TaskDependency.blocker_id)
        .where(Task.status != "done")
        .distinct()
    )

    result = await db.execute(
        select(Task).where(Task.id.in_(blocked_subq), Task.status.in_(["todo", "in_progress"]))
    )
    blocked_tasks = list(result.scalars().all())

    output = []
    for task in blocked_tasks:
        blockers_result = await db.execute(
            select(Task)
            .join(TaskDependency, TaskDependency.blocker_id == Task.id)
            .where(TaskDependency.blocked_id == task.id, Task.status != "done")
        )
        blockers = list(blockers_result.scalars().all())
        output.append({
            "id": task.id,
            "title": task.title,
            "project_id": task.project_id,
            "blocked_by": [{"id": b.id, "title": b.title, "status": b.status} for b in blockers],
        })

    return output
