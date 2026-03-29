from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from logbook.database import get_db
from logbook.schemas import ItemResponse, ListResponse, Meta, ProjectCounts, ProjectCreate, ProjectOut, ProjectUpdate
from logbook.services import projects as svc

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ItemResponse)
async def create_project(body: ProjectCreate, db: AsyncSession = Depends(get_db)):
    project = await svc.create_project(db, name=body.name, description=body.description, motivation=body.motivation, tags=body.tags)
    tags = await svc.get_tags(db, "project", project.id)
    return ItemResponse(data=ProjectOut(
        id=project.id, name=project.name, description=project.description,
        motivation=project.motivation, status=project.status, tags=tags,
        created_at=project.created_at, updated_at=project.updated_at,
    ))


@router.get("", response_model=ListResponse)
async def list_projects(status: str | None = None, db: AsyncSession = Depends(get_db)):
    projects = await svc.list_projects(db, status=status)
    tags_map = await svc.get_tags_batch(db, "project", [p.id for p in projects])
    items = [
        ProjectOut(
            id=p.id, name=p.name, description=p.description,
            motivation=p.motivation, status=p.status, tags=tags_map.get(p.id, []),
            created_at=p.created_at, updated_at=p.updated_at,
        )
        for p in projects
    ]
    return ListResponse(data=items, meta=Meta(total=len(items), limit=len(items), offset=0))


@router.get("/{project_id}", response_model=ItemResponse)
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)):
    project = await svc.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    tags = await svc.get_tags(db, "project", project.id)
    counts = await svc.get_project_counts(db, project_id)
    return ItemResponse(data=ProjectOut(
        id=project.id, name=project.name, description=project.description,
        motivation=project.motivation, status=project.status, tags=tags,
        counts=ProjectCounts(**counts),
        created_at=project.created_at, updated_at=project.updated_at,
    ))


@router.patch("/{project_id}", response_model=ItemResponse)
async def update_project(project_id: str, body: ProjectUpdate, db: AsyncSession = Depends(get_db)):
    project = await svc.update_project(db, project_id, **body.model_dump(exclude_none=True))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    tags = await svc.get_tags(db, "project", project.id)
    return ItemResponse(data=ProjectOut(
        id=project.id, name=project.name, description=project.description,
        motivation=project.motivation, status=project.status, tags=tags,
        created_at=project.created_at, updated_at=project.updated_at,
    ))


@router.delete("/{project_id}")
async def delete_project(project_id: str, db: AsyncSession = Depends(get_db)):
    deleted = await svc.delete_project(db, project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"data": {"deleted": True}}
