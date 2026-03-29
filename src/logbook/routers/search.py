from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from logbook.database import get_db
from logbook.models import Project, Task, WorkLogEntry
from logbook.schemas import ItemResponse, SearchResponse, SearchResult
from logbook.services import search as svc

router = APIRouter(tags=["search"])


@router.get("/search", response_model=ItemResponse)
async def search(
    q: str = Query(..., description="Search query"),
    type: str | None = Query(None, description="Filter by entity type (comma-separated: project,task,goal,work_log_entry)"),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    entity_types = [t.strip() for t in type.split(",")] if type else None
    results = await svc.search(db, query=q, entity_types=entity_types, limit=limit)

    # Enrich work_log_entry results with project name and timestamp
    pname_cache: dict[str, str] = {}
    enriched = []
    for r in results:
        extra: dict = {}
        if r["entity_type"] == "work_log_entry":
            entry = await db.get(WorkLogEntry, r["entity_id"])
            if entry:
                extra["created_at"] = entry.created_at
                if entry.project_id:
                    if entry.project_id not in pname_cache:
                        proj = await db.get(Project, entry.project_id)
                        pname_cache[entry.project_id] = proj.name if proj else None
                    extra["project_name"] = pname_cache[entry.project_id]
        elif r["entity_type"] == "task":
            task = await db.get(Task, r["entity_id"])
            if task and task.project_id:
                if task.project_id not in pname_cache:
                    proj = await db.get(Project, task.project_id)
                    pname_cache[task.project_id] = proj.name if proj else None
                extra["project_name"] = pname_cache[task.project_id]
        enriched.append(SearchResult(**r, **extra))

    return ItemResponse(data=SearchResponse(
        query=q,
        total=len(results),
        results=enriched,
    ))
