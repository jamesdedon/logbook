import pytest
from httpx import AsyncClient
from sqlalchemy import text


@pytest.fixture
async def seeded(client: AsyncClient, db):
    # Create FTS table and triggers in test DB
    await db.execute(text("""
        CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(
            entity_type, entity_id, title, body,
            tokenize='porter unicode61'
        )
    """))
    for table, trigger_name, etype, title_col, body_col in [
        ("projects", "projects", "project", "NEW.name", "NEW.description"),
        ("goals", "goals", "goal", "NEW.title", "NEW.description"),
        ("tasks", "tasks", "task", "NEW.title", "NEW.description"),
        ("work_log_entries", "worklog", "work_log_entry", "NEW.description", "COALESCE(NEW.metadata, '')"),
    ]:
        await db.execute(text(f"""
            CREATE TRIGGER IF NOT EXISTS search_{trigger_name}_insert AFTER INSERT ON {table} BEGIN
                INSERT INTO search_index(entity_type, entity_id, title, body)
                VALUES ('{etype}', NEW.id, {title_col}, {body_col});
            END
        """))
    await db.commit()

    # Seed data
    resp = await client.post("/projects", json={"name": "authentication service", "description": "handles user auth and sessions"})
    pid = resp.json()["data"]["id"]
    await client.post(f"/projects/{pid}/goals", json={"title": "deploy auth to production"})
    await client.post(f"/projects/{pid}/tasks", json={"title": "implement JWT token refresh", "priority": "high"})
    await client.post(f"/projects/{pid}/tasks", json={"title": "write database migration", "priority": "medium"})
    await client.post("/log", json={"description": "refactored authentication middleware", "project_id": pid})
    await client.post("/log", json={"description": "fixed database connection pooling bug"})
    return pid


@pytest.mark.asyncio
async def test_search_basic(client: AsyncClient, seeded):
    resp = await client.get("/search", params={"q": "auth"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] >= 3  # project, goal, task, and/or log entry


@pytest.mark.asyncio
async def test_search_filters_by_type(client: AsyncClient, seeded):
    resp = await client.get("/search", params={"q": "auth", "type": "task"})
    data = resp.json()["data"]
    assert all(r["entity_type"] == "task" for r in data["results"])


@pytest.mark.asyncio
async def test_search_database(client: AsyncClient, seeded):
    resp = await client.get("/search", params={"q": "database"})
    data = resp.json()["data"]
    assert data["total"] >= 2  # task + log entry


@pytest.mark.asyncio
async def test_search_no_results(client: AsyncClient, seeded):
    resp = await client.get("/search", params={"q": "xyznonexistent"})
    data = resp.json()["data"]
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_search_stemming(client: AsyncClient, seeded):
    # "refreshing" should match "refresh" due to porter stemming
    resp = await client.get("/search", params={"q": "refreshing"})
    data = resp.json()["data"]
    assert data["total"] >= 1
