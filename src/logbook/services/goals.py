from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from logbook.models import Goal


async def create_goal(
    db: AsyncSession,
    project_id: str,
    title: str,
    description: str = "",
    motivation: str = "",
    target_date: str | None = None,
) -> Goal:
    goal = Goal(project_id=project_id, title=title, description=description, motivation=motivation, target_date=target_date)
    db.add(goal)
    await db.commit()
    await db.refresh(goal)
    return goal


async def list_goals(db: AsyncSession, project_id: str, status: str | None = None) -> list[Goal]:
    stmt = select(Goal).where(Goal.project_id == project_id)
    if status:
        stmt = stmt.where(Goal.status == status)
    else:
        stmt = stmt.where(Goal.status == "active")
    stmt = stmt.order_by(Goal.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_goal(db: AsyncSession, goal_id: str) -> Goal | None:
    return await db.get(Goal, goal_id)


async def update_goal(db: AsyncSession, goal_id: str, **kwargs) -> Goal | None:
    goal = await db.get(Goal, goal_id)
    if not goal:
        return None
    for key, value in kwargs.items():
        if value is not None:
            setattr(goal, key, value)
    await db.commit()
    await db.refresh(goal)
    return goal


async def delete_goal(db: AsyncSession, goal_id: str) -> bool:
    goal = await db.get(Goal, goal_id)
    if not goal:
        return False
    await db.delete(goal)
    await db.commit()
    return True
