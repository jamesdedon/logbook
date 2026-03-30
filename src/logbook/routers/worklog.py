import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from logbook.database import get_db
from logbook.schemas import ItemResponse, ListResponse, Meta, WorkLogCreate, WorkLogOut, WorkLogUpdate
from logbook.services import projects as project_svc
from logbook.services import worklog as svc

router = APIRouter(prefix="/log", tags=["worklog"])


def _entry_to_out(entry, tags: list[str] | None = None) -> WorkLogOut:
    metadata = json.loads(entry.metadata_json) if entry.metadata_json else {}
    return WorkLogOut(
        id=entry.id, project_id=entry.project_id, task_id=entry.task_id,
        description=entry.description, metadata=metadata, tags=tags or [],
        created_at=entry.created_at,
    )


@router.post("", response_model=ItemResponse)
async def create_entry(body: WorkLogCreate, db: AsyncSession = Depends(get_db)):
    entry = await svc.create_entry(
        db, description=body.description, project_id=body.project_id,
        task_id=body.task_id, metadata=body.metadata, tags=body.tags,
    )
    tags = await project_svc.get_tags(db, "work_log_entry", entry.id)
    return ItemResponse(data=_entry_to_out(entry, tags))


@router.get("", response_model=ListResponse)
async def list_entries(
    project_id: str | None = None,
    task_id: str | None = None,
    since: str | None = None,
    until: str | None = None,
    q: str | None = None,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    entries, total = await svc.list_entries(
        db, project_id=project_id, task_id=task_id, since=since,
        until=until, q=q, limit=limit, offset=offset,
    )
    tags_map = await project_svc.get_tags_batch(db, "work_log_entry", [e.id for e in entries])
    items = [_entry_to_out(e, tags_map.get(e.id, [])) for e in entries]
    return ListResponse(data=items, meta=Meta(total=total, limit=limit, offset=offset))


@router.get("/{entry_id}", response_model=ItemResponse)
async def get_entry(entry_id: str, db: AsyncSession = Depends(get_db)):
    entry = await svc.get_entry(db, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    tags = await project_svc.get_tags(db, "work_log_entry", entry.id)
    return ItemResponse(data=_entry_to_out(entry, tags))


@router.patch("/{entry_id}", response_model=ItemResponse)
async def update_entry(entry_id: str, body: WorkLogUpdate, db: AsyncSession = Depends(get_db)):
    entry = await svc.update_entry(db, entry_id, **body.model_dump(exclude_unset=True))
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    tags = await project_svc.get_tags(db, "work_log_entry", entry.id)
    return ItemResponse(data=_entry_to_out(entry, tags))


@router.delete("/{entry_id}")
async def delete_entry(entry_id: str, db: AsyncSession = Depends(get_db)):
    deleted = await svc.delete_entry(db, entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"data": {"deleted": True}}
