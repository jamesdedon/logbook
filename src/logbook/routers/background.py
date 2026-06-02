from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from logbook.config import settings
from logbook.schemas import ItemResponse
from logbook.services import background as svc

router = APIRouter(tags=["background"])

_MEDIA_TYPES = {".png": "image/png", ".jpg": "image/jpeg"}


@router.get("/background")
async def get_background():
    path = svc.background_path(settings.home)
    if path is None:
        raise HTTPException(status_code=404, detail="No background image set")
    return FileResponse(
        path,
        media_type=_MEDIA_TYPES.get(path.suffix, "application/octet-stream"),
        headers={"Cache-Control": "no-cache"},
    )


@router.put("/background", response_model=ItemResponse)
async def put_background(request: Request):
    data = await request.body()
    if not data:
        raise HTTPException(status_code=400, detail="Empty request body")
    try:
        path = svc.save_background(settings.home, data)
    except ValueError as e:
        raise HTTPException(status_code=415, detail=str(e))
    return ItemResponse(data={"saved": True, "content_type": _MEDIA_TYPES[path.suffix]})


@router.delete("/background", response_model=ItemResponse)
async def delete_background():
    deleted = svc.delete_background(settings.home)
    return ItemResponse(data={"deleted": deleted})
