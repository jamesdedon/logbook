import pytest
from httpx import AsyncClient


@pytest.fixture
async def project_id(client: AsyncClient) -> str:
    resp = await client.post("/projects", json={"name": "summary-proj"})
    return resp.json()["data"]["id"]


@pytest.mark.asyncio
async def test_summary(client: AsyncClient, project_id: str):
    await client.post(f"/projects/{project_id}/tasks", json={"title": "Task 1", "priority": "high"})
    await client.post("/log", json={"description": "Did stuff", "project_id": project_id})

    resp = await client.get("/summary")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["generated_at"]
    assert len(data["active_projects"]) == 1
    assert data["active_projects"][0]["name"] == "summary-proj"


@pytest.mark.asyncio
async def test_today(client: AsyncClient, project_id: str):
    await client.post("/log", json={"description": "Today's work", "project_id": project_id})
    resp = await client.get("/summary/today")
    assert resp.status_code == 200
    assert len(resp.json()["data"]["log_entries"]) >= 1


@pytest.mark.asyncio
async def test_next(client: AsyncClient, project_id: str):
    await client.post(f"/projects/{project_id}/tasks", json={"title": "Do this", "priority": "critical"})
    await client.post(f"/projects/{project_id}/tasks", json={"title": "Then this", "priority": "low"})

    resp = await client.get("/summary/next")
    assert resp.status_code == 200
    tasks = resp.json()["data"]["tasks"]
    assert len(tasks) >= 2
    assert tasks[0]["priority"] == "critical"


@pytest.mark.asyncio
async def test_blocked(client: AsyncClient, project_id: str):
    r1 = await client.post(f"/projects/{project_id}/tasks", json={"title": "Blocker"})
    blocker_id = r1.json()["data"]["id"]
    await client.post(
        f"/projects/{project_id}/tasks",
        json={"title": "Blocked", "blocked_by": [blocker_id]},
    )

    resp = await client.get("/summary/blocked")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["title"] == "Blocked"
