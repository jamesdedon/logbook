from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from setproctitle import setproctitle

from logbook.routers import background, goals, projects, search, summary, tasks, worklog

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setproctitle("logbook")
    yield


app = FastAPI(title="Logbook", version="0.1.0", lifespan=lifespan)

app.include_router(projects.router)
app.include_router(goals.router)
app.include_router(tasks.router)
app.include_router(worklog.router)
app.include_router(summary.router)
app.include_router(search.router)
app.include_router(background.router)


app.mount("/ui", StaticFiles(directory=STATIC_DIR, html=True), name="ui")


@app.middleware("http")
async def revalidate_ui_assets(request, call_next):
    """Force the browser to revalidate /ui assets on every load.

    StaticFiles sends only ETag/Last-Modified, so without an explicit
    Cache-Control browsers fall back to heuristic freshness and can serve a
    stale app.js against a fresh index.html.  "no-cache" means revalidate,
    not don't-store — the ETag still turns repeat loads into cheap 304s.
    """
    response = await call_next(request)
    if request.url.path.startswith("/ui"):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/health")
async def health():
    return {"status": "ok"}
