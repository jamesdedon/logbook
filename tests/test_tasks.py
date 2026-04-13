import pytest
from httpx import AsyncClient


@pytest.fixture
async def project_id(client: AsyncClient) -> str:
    resp = await client.post("/projects", json={"name": "task-test-proj"})
    return resp.json()["data"]["id"]


@pytest.mark.asyncio
async def test_create_task(client: AsyncClient, project_id: str):
    resp = await client.post(
        f"/projects/{project_id}/tasks",
        json={"title": "Build API", "priority": "high"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["title"] == "Build API"
    assert data["priority"] == "high"
    assert data["status"] == "todo"


@pytest.mark.asyncio
async def test_task_dependencies(client: AsyncClient, project_id: str):
    # Create blocker task
    r1 = await client.post(f"/projects/{project_id}/tasks", json={"title": "Design schema"})
    blocker_id = r1.json()["data"]["id"]

    # Create blocked task
    r2 = await client.post(
        f"/projects/{project_id}/tasks",
        json={"title": "Implement models", "blocked_by": [blocker_id]},
    )
    blocked_id = r2.json()["data"]["id"]

    # Verify blocked
    detail = await client.get(f"/tasks/{blocked_id}")
    data = detail.json()["data"]
    assert data["is_blocked"] is True
    assert len(data["blocked_by"]) == 1
    assert data["blocked_by"][0]["id"] == blocker_id

    # Complete blocker
    await client.patch(f"/tasks/{blocker_id}", json={"status": "done"})

    # Now unblocked
    detail2 = await client.get(f"/tasks/{blocked_id}")
    assert detail2.json()["data"]["is_blocked"] is False


@pytest.mark.asyncio
async def test_list_tasks_filter(client: AsyncClient, project_id: str):
    await client.post(f"/projects/{project_id}/tasks", json={"title": "T1", "priority": "high"})
    await client.post(f"/projects/{project_id}/tasks", json={"title": "T2", "priority": "low"})

    resp = await client.get("/tasks", params={"priority": "high"})
    assert resp.json()["meta"]["total"] == 1
    assert resp.json()["data"][0]["title"] == "T1"


@pytest.mark.asyncio
async def test_complete_task_sets_completed_at(client: AsyncClient, project_id: str):
    r = await client.post(f"/projects/{project_id}/tasks", json={"title": "Finish me"})
    tid = r.json()["data"]["id"]
    resp = await client.patch(f"/tasks/{tid}", json={"status": "done"})
    assert resp.json()["data"]["completed_at"] is not None


@pytest.mark.asyncio
async def test_delete_task(client: AsyncClient, project_id: str):
    r = await client.post(f"/projects/{project_id}/tasks", json={"title": "Delete me"})
    tid = r.json()["data"]["id"]
    await client.delete(f"/tasks/{tid}")
    assert (await client.get(f"/tasks/{tid}")).status_code == 404


@pytest.mark.asyncio
async def test_add_remove_dependency(client: AsyncClient, project_id: str):
    r1 = await client.post(f"/projects/{project_id}/tasks", json={"title": "A"})
    r2 = await client.post(f"/projects/{project_id}/tasks", json={"title": "B"})
    a_id = r1.json()["data"]["id"]
    b_id = r2.json()["data"]["id"]

    # Add dep
    await client.post(f"/tasks/{b_id}/dependencies", json={"blocker_id": a_id})
    detail = await client.get(f"/tasks/{b_id}")
    assert detail.json()["data"]["is_blocked"] is True

    # Remove dep
    await client.delete(f"/tasks/{b_id}/dependencies/{a_id}")
    detail2 = await client.get(f"/tasks/{b_id}")
    assert detail2.json()["data"]["is_blocked"] is False


@pytest.mark.asyncio
async def test_batch_create_tasks(client: AsyncClient, project_id: str):
    payload = {
        "tasks": [
            {"title": "Batch A", "priority": "high", "rationale": "first"},
            {"title": "Batch B", "priority": "low"},
            {"title": "Batch C", "description": "third", "tags": ["seed"]},
        ]
    }
    resp = await client.post(f"/projects/{project_id}/tasks/batch", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["meta"]["total"] == 3
    titles = [t["title"] for t in body["data"]]
    assert titles == ["Batch A", "Batch B", "Batch C"]
    assert body["data"][0]["priority"] == "high"
    assert body["data"][2]["tags"] == ["seed"]
    for t in body["data"]:
        assert t["project_id"] == project_id
        assert t["status"] == "todo"


@pytest.mark.asyncio
async def test_batch_create_with_preexisting_blocker(client: AsyncClient, project_id: str):
    # Create a blocker first
    r = await client.post(f"/projects/{project_id}/tasks", json={"title": "Seed blocker"})
    blocker_id = r.json()["data"]["id"]

    payload = {"tasks": [{"title": "Downstream", "blocked_by": [blocker_id]}]}
    resp = await client.post(f"/projects/{project_id}/tasks/batch", json=payload)
    assert resp.status_code == 200
    downstream_id = resp.json()["data"][0]["id"]

    detail = await client.get(f"/tasks/{downstream_id}")
    assert detail.json()["data"]["is_blocked"] is True
    assert detail.json()["data"]["blocked_by"][0]["id"] == blocker_id


@pytest.mark.asyncio
async def test_batch_create_empty_list_rejected(client: AsyncClient, project_id: str):
    resp = await client.post(f"/projects/{project_id}/tasks/batch", json={"tasks": []})
    assert resp.status_code == 400
