from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from logbook.config import settings
from logbook.models import Goal, Project, Task, TaskDependency, WorkLogEntry


async def get_summary(db: AsyncSession) -> dict:
    # Active projects
    projects_result = await db.execute(select(Project).where(Project.status == "active"))
    projects = list(projects_result.scalars().all())
    project_ids = [p.id for p in projects]

    # Bulk: active goal counts per project
    goals_result = await db.execute(
        select(Goal.project_id, func.count())
        .where(Goal.project_id.in_(project_ids), Goal.status == "active")
        .group_by(Goal.project_id)
    )
    goals_by_project = dict(goals_result.all())

    # Bulk: task counts per project per status
    tasks_result = await db.execute(
        select(Task.project_id, Task.status, func.count())
        .where(Task.project_id.in_(project_ids))
        .group_by(Task.project_id, Task.status)
    )
    task_counts_by_project: dict[str, dict[str, int]] = {}
    for pid, status, count in tasks_result.all():
        task_counts_by_project.setdefault(pid, {})[status] = count

    # Bulk: blocked task counts per project
    blocked_subq = (
        select(TaskDependency.blocked_id)
        .join(Task, Task.id == TaskDependency.blocker_id)
        .where(Task.status != "done")
    )
    blocked_result = await db.execute(
        select(Task.project_id, func.count())
        .where(
            Task.project_id.in_(project_ids),
            Task.status.in_(["todo", "in_progress"]),
            Task.id.in_(blocked_subq),
        )
        .group_by(Task.project_id)
    )
    blocked_by_project = dict(blocked_result.all())

    active_projects = []
    for p in projects:
        tc = task_counts_by_project.get(p.id, {})
        active_projects.append({
            "id": p.id,
            "name": p.name,
            "motivation": p.motivation or "",
            "goals_active": goals_by_project.get(p.id, 0),
            "tasks_summary": {
                "todo": tc.get("todo", 0),
                "in_progress": tc.get("in_progress", 0),
                "done": tc.get("done", 0),
                "cancelled": tc.get("cancelled", 0),
            },
            "blocked_tasks": blocked_by_project.get(p.id, 0),
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

    tasks = [row[0] for row in rows]

    # Batch load project names
    project_ids = {t.project_id for t in tasks if t.project_id}
    if project_ids:
        proj_result = await db.execute(
            select(Project.id, Project.name).where(Project.id.in_(project_ids))
        )
        pname_map = dict(proj_result.all())
    else:
        pname_map = {}

    return [
        {
            "id": t.id,
            "title": t.title,
            "rationale": t.rationale or "",
            "priority": t.priority,
            "project_id": t.project_id,
            "project_name": pname_map.get(t.project_id, "unknown"),
        }
        for t in tasks
    ]


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
    log_result = await db.execute(log_stmt.order_by(WorkLogEntry.created_at.desc()))
    log_entries = list(log_result.scalars().all())

    # Tasks completed this week
    tasks_stmt = (
        select(Task)
        .where(Task.completed_at >= week_start_iso, Task.completed_at < week_end, Task.status == "done")
    )
    if project_id:
        tasks_stmt = tasks_stmt.where(Task.project_id == project_id)
    tasks_result = await db.execute(tasks_stmt.order_by(Task.completed_at.desc()))
    tasks_completed = list(tasks_result.scalars().all())

    # Tasks created this week
    tasks_created_stmt = (
        select(Task)
        .where(Task.created_at >= week_start_iso, Task.created_at < week_end)
    )
    if project_id:
        tasks_created_stmt = tasks_created_stmt.where(Task.project_id == project_id)
    tasks_created_result = await db.execute(tasks_created_stmt.order_by(Task.created_at.desc()))
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
    project_motivations = {}
    for pid in all_project_ids:
        proj = await db.get(Project, pid)
        project_names[pid] = proj.name if proj else "unknown"
        project_motivations[pid] = (proj.motivation or "") if proj else ""
    if "unlinked" in by_project:
        project_names["unlinked"] = "Unlinked"
        project_motivations["unlinked"] = ""

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
        "project_motivations": project_motivations,
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
    blocked_ids = [t.id for t in blocked_tasks]

    if not blocked_ids:
        return []

    # Batch load all blockers for all blocked tasks
    blockers_result = await db.execute(
        select(TaskDependency.blocked_id, Task)
        .join(Task, Task.id == TaskDependency.blocker_id)
        .where(TaskDependency.blocked_id.in_(blocked_ids), Task.status != "done")
    )
    blockers_by_task: dict[str, list] = {}
    for blocked_id, blocker in blockers_result.all():
        blockers_by_task.setdefault(blocked_id, []).append(blocker)

    return [
        {
            "id": task.id,
            "title": task.title,
            "project_id": task.project_id,
            "blocked_by": [
                {"id": b.id, "title": b.title, "status": b.status}
                for b in blockers_by_task.get(task.id, [])
            ],
        }
        for task in blocked_tasks
    ]
