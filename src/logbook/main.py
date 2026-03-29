from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from logbook.routers import goals, projects, search, summary, tasks, worklog

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield


app = FastAPI(title="Logbook", version="0.1.0", lifespan=lifespan)

app.include_router(projects.router)
app.include_router(goals.router)
app.include_router(tasks.router)
app.include_router(worklog.router)
app.include_router(summary.router)
app.include_router(search.router)


app.mount("/ui", StaticFiles(directory=STATIC_DIR, html=True), name="ui")


@app.get("/health")
async def health():
    return {"status": "ok"}
