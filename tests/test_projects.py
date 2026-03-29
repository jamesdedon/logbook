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


@pytest.mark.asyncio
async def test_archive_unarchive_project(client: AsyncClient):
    resp = await client.post("/projects", json={"name": "lifecycle-proj"})
    pid = resp.json()["data"]["id"]
    assert resp.json()["data"]["status"] == "active"

    # Archive
    resp = await client.patch(f"/projects/{pid}", json={"status": "archived"})
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "archived"

    # Hidden from default list
    resp = await client.get("/projects")
    assert all(p["id"] != pid for p in resp.json()["data"])

    # Unarchive
    resp = await client.patch(f"/projects/{pid}", json={"status": "active"})
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "active"

    # Visible again
    resp = await client.get("/projects")
    assert any(p["id"] == pid for p in resp.json()["data"])


@pytest.mark.asyncio
async def test_list_projects_status_all(client: AsyncClient):
    await client.post("/projects", json={"name": "active-proj"})
    resp2 = await client.post("/projects", json={"name": "archived-proj"})
    archived_id = resp2.json()["data"]["id"]
    await client.patch(f"/projects/{archived_id}", json={"status": "archived"})

    # Default: active only
    resp = await client.get("/projects")
    assert resp.json()["meta"]["total"] == 1
    assert resp.json()["data"][0]["name"] == "active-proj"

    # status=all: both
    resp = await client.get("/projects", params={"status": "all"})
    assert resp.json()["meta"]["total"] == 2

    # status=archived: archived only
    resp = await client.get("/projects", params={"status": "archived"})
    assert resp.json()["meta"]["total"] == 1
    assert resp.json()["data"][0]["name"] == "archived-proj"
