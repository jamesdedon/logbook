import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi.responses import PlainTextResponse

from logbook.config import settings
from logbook.database import get_db
from logbook.schemas import (
    BlockedTaskOut,
    DaySummary,
    ItemResponse,
    NextAction,
    NextOut,
    ProjectSummary,
    ProjectWeekSummary,
    SummaryOut,
    TaskDepRef,
    TaskOut,
    TodayOut,
    WeeklyReportOut,
    WorkLogOut,
)
from logbook.models import Project
from logbook.services import summary as svc
from logbook.services.export import export_weekly_markdown

router = APIRouter(prefix="/summary", tags=["summary"])


def _to_local(iso_str: str) -> str:
    """Convert a UTC ISO-8601 timestamp to local timezone."""
    try:
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(settings.tz).isoformat()
    except (ValueError, TypeError):
        return iso_str


@router.get("", response_model=ItemResponse)
async def get_summary(db: AsyncSession = Depends(get_db)):
    data = await svc.get_summary(db)
    now = datetime.now(timezone.utc).isoformat()

    return ItemResponse(data=SummaryOut(
        generated_at=now,
        active_projects=[ProjectSummary(**p) for p in data["active_projects"]],
        recent_activity=[
            WorkLogOut(
                id=e.id, project_id=e.project_id, task_id=e.task_id,
                description=e.description,
                metadata=json.loads(e.metadata_json) if e.metadata_json else {},
                created_at=_to_local(e.created_at),
            )
            for e in data["recent_activity"]
        ],
        blocked_tasks=[
            BlockedTaskOut(
                id=bt["id"], title=bt["title"], project_id=bt["project_id"],
                blocked_by=[TaskDepRef(**b) for b in bt["blocked_by"]],
            )
            for bt in data["blocked_tasks"]
        ],
        next_actions=[NextAction(**n) for n in data["next_actions"]],
    ))


@router.get("/today", response_model=ItemResponse)
async def get_today(db: AsyncSession = Depends(get_db)):
    data = await svc.get_today(db)
    now = datetime.now(timezone.utc).isoformat()

    # Resolve project names for completed tasks
    pname_cache: dict[str, str] = {}
    for t in data["tasks_completed"]:
        if t.project_id and t.project_id not in pname_cache:
            p = await db.get(Project, t.project_id)
            pname_cache[t.project_id] = p.name if p else "Unknown"

    return ItemResponse(data=TodayOut(
        generated_at=now,
        log_entries=[
            WorkLogOut(
                id=e.id, project_id=e.project_id, task_id=e.task_id,
                description=e.description,
                metadata=json.loads(e.metadata_json) if e.metadata_json else {},
                created_at=_to_local(e.created_at),
            )
            for e in data["log_entries"]
        ],
        tasks_completed=[
            TaskOut(
                id=t.id, project_id=t.project_id,
                project_name=pname_cache.get(t.project_id, "Unknown"),
                goal_id=t.goal_id,
                title=t.title, description=t.description, rationale=t.rationale,
                status=t.status, priority=t.priority,
                created_at=_to_local(t.created_at), updated_at=t.updated_at,
                completed_at=t.completed_at,
            )
            for t in data["tasks_completed"]
        ],
    ))


@router.get("/next", response_model=ItemResponse)
async def get_next(db: AsyncSession = Depends(get_db)):
    next_actions = await svc.get_next_actions(db)
    now = datetime.now(timezone.utc).isoformat()
    return ItemResponse(data=NextOut(
        generated_at=now,
        tasks=[NextAction(**n) for n in next_actions],
    ))


@router.get("/weekly", response_model=ItemResponse)
async def get_weekly(weeks_back: int = 0, project_id: str | None = None, db: AsyncSession = Depends(get_db)):
    data = await svc.get_weekly_report(db, weeks_back=weeks_back, project_id=project_id)
    now = datetime.now(timezone.utc).isoformat()

    def _entry_out(e):
        return WorkLogOut(
            id=e.id, project_id=e.project_id, task_id=e.task_id,
            description=e.description,
            metadata=json.loads(e.metadata_json) if e.metadata_json else {},
            created_at=_to_local(e.created_at),
        )

    def _task_out(t):
        pname = data["project_names"].get(t.project_id, "Unknown")
        return TaskOut(
            id=t.id, project_id=t.project_id, project_name=pname,
            goal_id=t.goal_id,
            title=t.title, description=t.description, rationale=t.rationale,
            status=t.status, priority=t.priority,
            created_at=t.created_at, updated_at=t.updated_at,
            completed_at=t.completed_at,
        )

    days = [
        DaySummary(date=day, entry_count=len(entries), entries=[_entry_out(e) for e in entries])
        for day, entries in sorted(data["days"].items())
    ]

    by_project = [
        ProjectWeekSummary(
            project_id=pid, project_name=data["project_names"].get(pid, "unknown"),
            project_motivation=data["project_motivations"].get(pid, ""),
            entry_count=len(entries), entries=[_entry_out(e) for e in entries],
        )
        for pid, entries in data["by_project"].items()
    ]

    return ItemResponse(data=WeeklyReportOut(
        generated_at=now,
        week_start=data["week_start"],
        week_end=data["week_end"],
        total_log_entries=data["total_log_entries"],
        total_tasks_completed=data["total_tasks_completed"],
        total_tasks_created=data["total_tasks_created"],
        total_goals_completed=data["total_goals_completed"],
        days=days,
        by_project=by_project,
        tasks_completed=[_task_out(t) for t in data["tasks_completed"]],
        tasks_created=[_task_out(t) for t in data["tasks_created"]],
    ))


@router.get("/export/weekly", response_class=PlainTextResponse)
async def export_weekly(weeks_back: int = 0, project_id: str | None = None, db: AsyncSession = Depends(get_db)):
    markdown = await export_weekly_markdown(db, weeks_back=weeks_back, project_id=project_id)
    return PlainTextResponse(content=markdown, media_type="text/markdown")


@router.get("/blocked", response_model=ItemResponse)
async def get_blocked(db: AsyncSession = Depends(get_db)):
    blocked = await svc.get_blocked_tasks(db)
    return ItemResponse(data=[
        BlockedTaskOut(
            id=bt["id"], title=bt["title"], project_id=bt["project_id"],
            blocked_by=[TaskDepRef(**b) for b in bt["blocked_by"]],
        )
        for bt in blocked
    ])
