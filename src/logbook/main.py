from contextlib import asynccontextmanager

from fastapi import FastAPI

from logbook.routers import goals, projects, summary, tasks, worklog


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield


app = FastAPI(title="Logbook", version="0.1.0", lifespan=lifespan)

app.include_router(projects.router)
app.include_router(goals.router)
app.include_router(tasks.router)
app.include_router(worklog.router)
app.include_router(summary.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
