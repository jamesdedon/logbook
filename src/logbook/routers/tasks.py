import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from logbook.database import get_db
from logbook.schemas import (
    DependencyCreate,
    ItemResponse,
    ListResponse,
    LogEntryBrief,
    Meta,
    TaskCreate,
    TaskDepRef,
    TaskOut,
    TaskUpdate,
)
from logbook.models import Project
from logbook.services import projects as project_svc
from logbook.services import tasks as svc

router = APIRouter(tags=["tasks"])


async def _task_to_out(db: AsyncSession, task_id: str) -> TaskOut:
    task = await svc.get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    blockers = await svc.get_task_blockers(db, task_id)
    blockees = await svc.get_task_blockees(db, task_id)
    is_blocked = await svc.is_task_blocked(db, task_id)
    log_entries = await svc.get_recent_log_entries(db, task_id)
    tags = await project_svc.get_tags(db, "task", task_id)
    project = await db.get(Project, task.project_id)
    project_name = project.name if project else "Unknown"

    return TaskOut(
        id=task.id, project_id=task.project_id, project_name=project_name,
        goal_id=task.goal_id,
        title=task.title, description=task.description, rationale=task.rationale,
        status=task.status, priority=task.priority, tags=tags,
        blocked_by=[TaskDepRef(id=b.id, title=b.title, status=b.status) for b in blockers],
        blocks=[TaskDepRef(id=b.id, title=b.title, status=b.status) for b in blockees],
        is_blocked=is_blocked,
        recent_log_entries=[
            LogEntryBrief(id=e.id, description=e.description, created_at=e.created_at) for e in log_entries
        ],
        created_at=task.created_at, updated_at=task.updated_at, completed_at=task.completed_at,
    )


@router.post("/projects/{project_id}/tasks", response_model=ItemResponse)
async def create_task(project_id: str, body: TaskCreate, db: AsyncSession = Depends(get_db)):
    task = await svc.create_task(
        db, project_id=project_id, title=body.title, description=body.description,
        rationale=body.rationale, priority=body.priority, goal_id=body.goal_id,
        tags=body.tags, blocked_by=body.blocked_by,
    )
    out = await _task_to_out(db, task.id)
    return ItemResponse(data=out)


@router.get("/tasks", response_model=ListResponse)
async def list_tasks(
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
    db: AsyncSession = Depends(get_db),
):
    tasks, total = await svc.list_tasks(
        db, project_id=project_id, goal_id=goal_id, status=status,
        priority=priority, blocked=blocked, tag=tag, q=q, sort=sort,
        limit=limit, offset=offset,
    )
    # Batch-resolve project names
    pname_cache: dict[str, str] = {}
    for t in tasks:
        if t.project_id not in pname_cache:
            p = await db.get(Project, t.project_id)
            pname_cache[t.project_id] = p.name if p else "Unknown"
    items = []
    for t in tasks:
        tags = await project_svc.get_tags(db, "task", t.id)
        items.append(TaskOut(
            id=t.id, project_id=t.project_id, project_name=pname_cache[t.project_id],
            goal_id=t.goal_id,
            title=t.title, description=t.description, rationale=t.rationale,
            status=t.status, priority=t.priority, tags=tags,
            created_at=t.created_at, updated_at=t.updated_at, completed_at=t.completed_at,
        ))
    return ListResponse(data=items, meta=Meta(total=total, limit=limit, offset=offset))


@router.get("/projects/{project_id}/tasks", response_model=ListResponse)
async def list_project_tasks(
    project_id: str,
    status: str | None = None,
    priority: str | None = None,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    tasks, total = await svc.list_tasks(
        db, project_id=project_id, status=status, priority=priority,
        limit=limit, offset=offset,
    )
    project = await db.get(Project, project_id)
    pname = project.name if project else "Unknown"
    items = []
    for t in tasks:
        tags = await project_svc.get_tags(db, "task", t.id)
        items.append(TaskOut(
            id=t.id, project_id=t.project_id, project_name=pname,
            goal_id=t.goal_id,
            title=t.title, description=t.description, rationale=t.rationale,
            status=t.status, priority=t.priority, tags=tags,
            created_at=t.created_at, updated_at=t.updated_at, completed_at=t.completed_at,
        ))
    return ListResponse(data=items, meta=Meta(total=total, limit=limit, offset=offset))


@router.get("/tasks/{task_id}", response_model=ItemResponse)
async def get_task(task_id: str, db: AsyncSession = Depends(get_db)):
    out = await _task_to_out(db, task_id)
    return ItemResponse(data=out)


@router.patch("/tasks/{task_id}", response_model=ItemResponse)
async def update_task(task_id: str, body: TaskUpdate, db: AsyncSession = Depends(get_db)):
    task = await svc.update_task(db, task_id, **body.model_dump(exclude_none=True))
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    out = await _task_to_out(db, task.id)
    return ItemResponse(data=out)


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str, db: AsyncSession = Depends(get_db)):
    deleted = await svc.delete_task(db, task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"data": {"deleted": True}}


@router.post("/tasks/{task_id}/dependencies", response_model=ItemResponse)
async def add_dependency(task_id: str, body: DependencyCreate, db: AsyncSession = Depends(get_db)):
    await svc.add_dependency(db, task_id=task_id, blocker_id=body.blocker_id)
    out = await _task_to_out(db, task_id)
    return ItemResponse(data=out)


@router.delete("/tasks/{task_id}/dependencies/{blocker_id}")
async def remove_dependency(task_id: str, blocker_id: str, db: AsyncSession = Depends(get_db)):
    removed = await svc.remove_dependency(db, task_id=task_id, blocker_id=blocker_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Dependency not found")
    return {"data": {"deleted": True}}
