from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from logbook.models import Goal, Project, Tag, Task


async def create_project(db: AsyncSession, name: str, description: str = "", tags: list[str] | None = None) -> Project:
    project = Project(name=name, description=description)
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
    if status:
        stmt = stmt.where(Project.status == status)
    else:
        stmt = stmt.where(Project.status == "active")
    stmt = stmt.order_by(Project.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_project(db: AsyncSession, project_id: str) -> Project | None:
    return await db.get(Project, project_id)


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
