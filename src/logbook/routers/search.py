from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from logbook.database import get_db
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
    return ItemResponse(data=SearchResponse(
        query=q,
        total=len(results),
        results=[SearchResult(**r) for r in results],
    ))
