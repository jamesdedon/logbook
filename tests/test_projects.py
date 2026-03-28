import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_project(client: AsyncClient):
    resp = await client.post("/projects", json={"name": "test-project", "description": "A test"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["name"] == "test-project"
    assert data["description"] == "A test"
    assert data["status"] == "active"
    assert data["id"]


@pytest.mark.asyncio
async def test_list_projects(client: AsyncClient):
    await client.post("/projects", json={"name": "proj-1"})
    await client.post("/projects", json={"name": "proj-2"})
    resp = await client.get("/projects")
    assert resp.status_code == 200
    assert resp.json()["meta"]["total"] == 2


@pytest.mark.asyncio
async def test_get_project(client: AsyncClient):
    create_resp = await client.post("/projects", json={"name": "detail-proj"})
    pid = create_resp.json()["data"]["id"]
    resp = await client.get(f"/projects/{pid}")
    assert resp.status_code == 200
    assert resp.json()["data"]["counts"]["goals"] == 0


@pytest.mark.asyncio
async def test_update_project(client: AsyncClient):
    create_resp = await client.post("/projects", json={"name": "old-name"})
    pid = create_resp.json()["data"]["id"]
    resp = await client.patch(f"/projects/{pid}", json={"name": "new-name"})
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "new-name"


@pytest.mark.asyncio
async def test_delete_project(client: AsyncClient):
    create_resp = await client.post("/projects", json={"name": "doomed"})
    pid = create_resp.json()["data"]["id"]
    resp = await client.delete(f"/projects/{pid}")
    assert resp.status_code == 200
    get_resp = await client.get(f"/projects/{pid}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_project_not_found(client: AsyncClient):
    resp = await client.get("/projects/nonexistent")
    assert resp.status_code == 404
