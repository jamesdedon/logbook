import pytest
from httpx import AsyncClient


@pytest.fixture
async def project_id(client: AsyncClient) -> str:
    resp = await client.post("/projects", json={"name": "goal-test-proj"})
    return resp.json()["data"]["id"]


@pytest.mark.asyncio
async def test_create_goal(client: AsyncClient, project_id: str):
    resp = await client.post(f"/projects/{project_id}/goals", json={"title": "Ship v0"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["title"] == "Ship v0"
    assert data["status"] == "active"


@pytest.mark.asyncio
async def test_list_goals(client: AsyncClient, project_id: str):
    await client.post(f"/projects/{project_id}/goals", json={"title": "Goal 1"})
    await client.post(f"/projects/{project_id}/goals", json={"title": "Goal 2"})
    resp = await client.get(f"/projects/{project_id}/goals")
    assert resp.json()["meta"]["total"] == 2


@pytest.mark.asyncio
async def test_update_goal(client: AsyncClient, project_id: str):
    create_resp = await client.post(f"/projects/{project_id}/goals", json={"title": "Old"})
    gid = create_resp.json()["data"]["id"]
    resp = await client.patch(f"/goals/{gid}", json={"title": "New", "status": "completed"})
    assert resp.json()["data"]["title"] == "New"
    assert resp.json()["data"]["status"] == "completed"


@pytest.mark.asyncio
async def test_delete_goal(client: AsyncClient, project_id: str):
    create_resp = await client.post(f"/projects/{project_id}/goals", json={"title": "Bye"})
    gid = create_resp.json()["data"]["id"]
    resp = await client.delete(f"/goals/{gid}")
    assert resp.status_code == 200
    assert (await client.get(f"/goals/{gid}")).status_code == 404
