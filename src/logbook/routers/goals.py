from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from logbook.database import get_db
from logbook.schemas import GoalCreate, GoalOut, GoalUpdate, ItemResponse, ListResponse, Meta
from logbook.services import goals as svc
from logbook.services.projects import resolve_project_id

router = APIRouter(tags=["goals"])


@router.post("/projects/{project_id}/goals", response_model=ItemResponse)
async def create_goal(project_id: str, body: GoalCreate, db: AsyncSession = Depends(get_db)):
    project_id = await resolve_project_id(db, project_id)
    goal = await svc.create_goal(
        db, project_id=project_id, title=body.title,
        description=body.description, motivation=body.motivation,
        target_date=body.target_date,
    )
    return ItemResponse(data=GoalOut(
        id=goal.id, project_id=goal.project_id, title=goal.title,
        description=goal.description, motivation=goal.motivation,
        status=goal.status, target_date=goal.target_date,
        created_at=goal.created_at, updated_at=goal.updated_at,
    ))


@router.get("/projects/{project_id}/goals", response_model=ListResponse)
async def list_goals(project_id: str, status: str | None = None, db: AsyncSession = Depends(get_db)):
    project_id = await resolve_project_id(db, project_id)
    goals = await svc.list_goals(db, project_id=project_id, status=status)
    items = [
        GoalOut(
            id=g.id, project_id=g.project_id, title=g.title,
            description=g.description, motivation=g.motivation,
            status=g.status, target_date=g.target_date,
            created_at=g.created_at, updated_at=g.updated_at,
        )
        for g in goals
    ]
    return ListResponse(data=items, meta=Meta(total=len(items), limit=len(items), offset=0))


@router.get("/goals/{goal_id}", response_model=ItemResponse)
async def get_goal(goal_id: str, db: AsyncSession = Depends(get_db)):
    goal = await svc.get_goal(db, goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return ItemResponse(data=GoalOut(
        id=goal.id, project_id=goal.project_id, title=goal.title,
        description=goal.description, motivation=goal.motivation,
        status=goal.status, target_date=goal.target_date,
        created_at=goal.created_at, updated_at=goal.updated_at,
    ))


@router.patch("/goals/{goal_id}", response_model=ItemResponse)
async def update_goal(goal_id: str, body: GoalUpdate, db: AsyncSession = Depends(get_db)):
    goal = await svc.update_goal(db, goal_id, **body.model_dump(exclude_none=True))
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return ItemResponse(data=GoalOut(
        id=goal.id, project_id=goal.project_id, title=goal.title,
        description=goal.description, motivation=goal.motivation,
        status=goal.status, target_date=goal.target_date,
        created_at=goal.created_at, updated_at=goal.updated_at,
    ))


@router.delete("/goals/{goal_id}")
async def delete_goal(goal_id: str, db: AsyncSession = Depends(get_db)):
    deleted = await svc.delete_goal(db, goal_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Goal not found")
    return {"data": {"deleted": True}}
