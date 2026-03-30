import json

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from logbook.models import Tag, WorkLogEntry


async def create_entry(
    db: AsyncSession,
    description: str,
    project_id: str | None = None,
    task_id: str | None = None,
    metadata: dict | None = None,
    tags: list[str] | None = None,
) -> WorkLogEntry:
    entry = WorkLogEntry(
        description=description,
        project_id=project_id,
        task_id=task_id,
        metadata_json=json.dumps(metadata or {}),
    )
    db.add(entry)
    await db.flush()
    if tags:
        for t in tags:
            db.add(Tag(entity_type="work_log_entry", entity_id=entry.id, tag=t))
    await db.commit()
    await db.refresh(entry)
    return entry


async def list_entries(
    db: AsyncSession,
    project_id: str | None = None,
    task_id: str | None = None,
    since: str | None = None,
    until: str | None = None,
    q: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[WorkLogEntry], int]:
    stmt = select(WorkLogEntry)
    count_stmt = select(func.count()).select_from(WorkLogEntry)

    filters = []
    if project_id:
        filters.append(WorkLogEntry.project_id == project_id)
    if task_id:
        filters.append(WorkLogEntry.task_id == task_id)
    if since:
        filters.append(WorkLogEntry.created_at >= since)
    if until:
        filters.append(WorkLogEntry.created_at <= until)
    if q:
        filters.append(WorkLogEntry.description.ilike(f"%{q}%"))

    for f in filters:
        stmt = stmt.where(f)
        count_stmt = count_stmt.where(f)

    stmt = stmt.order_by(WorkLogEntry.created_at.desc()).limit(limit).offset(offset)

    total = await db.scalar(count_stmt) or 0
    result = await db.execute(stmt)
    return list(result.scalars().all()), total


async def get_entry(db: AsyncSession, entry_id: str) -> WorkLogEntry | None:
    return await db.get(WorkLogEntry, entry_id)


async def update_entry(db: AsyncSession, entry_id: str, **kwargs) -> WorkLogEntry | None:
    entry = await db.get(WorkLogEntry, entry_id)
    if not entry:
        return None
    if "description" in kwargs and kwargs["description"] is not None:
        entry.description = kwargs["description"]
    if "project_id" in kwargs:
        entry.project_id = kwargs["project_id"]
    if "task_id" in kwargs:
        entry.task_id = kwargs["task_id"]
    if "metadata" in kwargs and kwargs["metadata"] is not None:
        entry.metadata_json = json.dumps(kwargs["metadata"])
    await db.commit()
    await db.refresh(entry)
    return entry


async def delete_entry(db: AsyncSession, entry_id: str) -> bool:
    entry = await db.get(WorkLogEntry, entry_id)
    if not entry:
        return False
    await db.delete(entry)
    await db.commit()
    return True
