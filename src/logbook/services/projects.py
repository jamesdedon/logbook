from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from logbook.models import Goal, Project, Tag, Task


async def create_project(db: AsyncSession, name: str, description: str = "", motivation: str = "", tags: list[str] | None = None) -> Project:
    project = Project(name=name, description=description, motivation=motivation)
    db.add(project)
    await db.flush()
    if tags:
        for t in tags:
            db.add(Tag(entity_type="project", entity_id=project.id, tag=t))
    await db.commit()
    await db.refresh(project)
    return project


async def list_projects(db: AsyncSession, status: str | None = None) -> list[Project]:
    stmt = select(Project)
    if status and status != "all":
        stmt = stmt.where(Project.status == status)
    elif not status:
        stmt = stmt.where(Project.status == "active")
    stmt = stmt.order_by(Project.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_project(db: AsyncSession, project_id: str) -> Project | None:
    return await db.get(Project, project_id)


async def resolve_project_id(db: AsyncSession, project_id: str) -> str:
    """Resolve a project identifier to its actual ID.

    Accepts a ULID (returned as-is if the project exists) or a case-insensitive
    project name.  Returns the canonical project ID, or the original string
    unchanged if no match is found.
    """
    # 1. Try exact ID lookup first (fast path)
    project = await db.get(Project, project_id)
    if project:
        return project.id

    # 2. Fall back to case-insensitive name match
    result = await db.execute(
        select(Project).where(func.lower(Project.name) == project_id.lower())
    )
    project = result.scalar_one_or_none()
    if project:
        return project.id

    return project_id  # unchanged – let downstream handle the miss


async def get_project_counts(db: AsyncSession, project_id: str) -> dict:
    goals_count = await db.scalar(
        select(func.count()).where(Goal.project_id == project_id, Goal.status == "active")
    )
    task_counts = {}
    for status in ("todo", "in_progress", "done", "cancelled"):
        count = await db.scalar(
            select(func.count()).where(Task.project_id == project_id, Task.status == status)
        )
        task_counts[f"tasks_{status}"] = count or 0
    return {"goals": goals_count or 0, **task_counts}


async def update_project(db: AsyncSession, project_id: str, **kwargs) -> Project | None:
    project = await db.get(Project, project_id)
    if not project:
        return None
    for key, value in kwargs.items():
        if value is not None:
            setattr(project, key, value)
    await db.commit()
    await db.refresh(project)
    return project


async def delete_project(db: AsyncSession, project_id: str) -> bool:
    project = await db.get(Project, project_id)
    if not project:
        return False
    await db.delete(project)
    await db.commit()
    return True


async def get_tags(db: AsyncSession, entity_type: str, entity_id: str) -> list[str]:
    result = await db.execute(
        select(Tag.tag).where(Tag.entity_type == entity_type, Tag.entity_id == entity_id)
    )
    return list(result.scalars().all())


async def get_tags_batch(db: AsyncSession, entity_type: str, entity_ids: list[str]) -> dict[str, list[str]]:
    """Load tags for multiple entities in a single query. Returns {entity_id: [tags]}."""
    if not entity_ids:
        return {}
    result = await db.execute(
        select(Tag.entity_id, Tag.tag)
        .where(Tag.entity_type == entity_type, Tag.entity_id.in_(entity_ids))
    )
    tags_map: dict[str, list[str]] = {eid: [] for eid in entity_ids}
    for entity_id, tag in result.all():
        tags_map[entity_id].append(tag)
    return tags_map
