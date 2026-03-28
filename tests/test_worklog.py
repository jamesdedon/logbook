import pytest
from httpx import AsyncClient


@pytest.fixture
async def project_id(client: AsyncClient) -> str:
    resp = await client.post("/projects", json={"name": "log-test-proj"})
    return resp.json()["data"]["id"]


@pytest.mark.asyncio
async def test_create_log_entry(client: AsyncClient, project_id: str):
    resp = await client.post("/log", json={
        "description": "Designed the schema",
        "project_id": project_id,
        "metadata": {"repo": "logbook", "commit": "abc123"},
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["description"] == "Designed the schema"
    assert data["metadata"]["commit"] == "abc123"


@pytest.mark.asyncio
async def test_list_log_entries(client: AsyncClient, project_id: str):
    await client.post("/log", json={"description": "Entry 1", "project_id": project_id})
    await client.post("/log", json={"description": "Entry 2", "project_id": project_id})
    resp = await client.get("/log", params={"project_id": project_id})
    assert resp.json()["meta"]["total"] == 2


@pytest.mark.asyncio
async def test_standalone_log_entry(client: AsyncClient):
    resp = await client.post("/log", json={"description": "Random thought"})
    assert resp.status_code == 200
    assert resp.json()["data"]["project_id"] is None


@pytest.mark.asyncio
async def test_update_log_entry(client: AsyncClient):
    r = await client.post("/log", json={"description": "Typo"})
    eid = r.json()["data"]["id"]
    resp = await client.patch(f"/log/{eid}", json={"description": "Fixed"})
    assert resp.json()["data"]["description"] == "Fixed"


@pytest.mark.asyncio
async def test_delete_log_entry(client: AsyncClient):
    r = await client.post("/log", json={"description": "Gone"})
    eid = r.json()["data"]["id"]
    await client.delete(f"/log/{eid}")
    assert (await client.get(f"/log/{eid}")).status_code == 404
