# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run all tests
uv run pytest tests/ -v

# Run a single test file
uv run pytest tests/test_tasks.py -v

# Run a single test
uv run pytest tests/test_tasks.py -k "test_task_dependencies" -v

# Install package (editable, with dev deps)
uv pip install -e ".[dev]"

# Run migrations
LOGBOOK_DB_PATH=./logbook.db uv run alembic upgrade head

# Start server locally
LOGBOOK_DB_PATH=./logbook.db uv run uvicorn logbook.main:app --host 127.0.0.1 --port 8000

# Restart the service (after install)
# macOS:
launchctl unload ~/Library/LaunchAgents/com.logbook.server.plist
launchctl load ~/Library/LaunchAgents/com.logbook.server.plist
# Linux:
systemctl --user restart logbook
```

## Architecture

Three-tier async Python app: **Routers → Services → Database**

- **Routers** (`src/logbook/routers/`) — Thin FastAPI handlers. Inject `AsyncSession` via `Depends(get_db)`, call service functions, wrap results in Pydantic schemas. Handle HTTP concerns only.
- **Services** (`src/logbook/services/`) — Business logic. Pure async functions that take a session and parameters. All DB queries live here. This layer is shared — the MCP server can import services directly in the future instead of going through HTTP.
- **Models** (`src/logbook/models.py`) — SQLAlchemy 2.0 ORM with `Mapped` columns. ULIDs for IDs, ISO-8601 strings for timestamps. Relationships use cascade deletes (project → goals/tasks) and set-null (goal deletion doesn't kill tasks).
- **Schemas** (`src/logbook/schemas.py`) — Pydantic models for all request/response shapes. Consistent envelope: `{"data": ...}` for singles, `{"data": [...], "meta": {...}}` for lists.

### Three interfaces to the same API

1. **REST API** (`src/logbook/main.py`) — FastAPI app, the source of truth.
2. **CLI** (`src/logbook/cli/main.py`) — Typer app that calls the REST API via httpx. Installed as `logbook` console script. Uses `LOGBOOK_URL` env var for the base URL.
3. **MCP Server** (`src/logbook/mcp_server.py`) — FastMCP app that also calls the REST API via httpx. Installed as `logbook-mcp` console script. Each tool returns formatted text, not JSON.

Both CLI and MCP are HTTP clients to the running server — they never import services directly.

### Search

FTS5 virtual table (`search_index`) with porter stemming. Kept in sync via SQLite triggers on all four content tables (created in migration 002). The search service auto-applies prefix matching unless the query contains FTS5 operators.

### Task dependencies

`task_dependencies` is a directed graph: `blocker_id` blocks `blocked_id`. A task is "blocked" if any of its blockers have `status != 'done'`. The `/summary/next` endpoint ranks unblocked tasks by priority → unblocks-count → age.

## Testing

Tests use pytest-asyncio with in-memory SQLite. `conftest.py` creates the schema via `Base.metadata.create_all()` (no alembic in tests). The `client` fixture overrides `get_db` with the test session and provides an httpx `AsyncClient` with ASGI transport.

Search tests need the FTS5 table and triggers created manually in the fixture since `metadata.create_all()` doesn't handle virtual tables.

## Adding a new entity or endpoint

1. Add the model to `models.py`
2. Add Pydantic schemas to `schemas.py`
3. Add service functions to `services/`
4. Add router to `routers/` and register it in `main.py`
5. Add a migration in `alembic/versions/` (increment the revision number, set `down_revision` to the previous one)
6. If searchable, add FTS5 triggers in the migration
7. Add CLI commands to `cli/main.py`
8. Add MCP tools to `mcp_server.py`
9. Add tests

## Logging work with git metadata

After committing code, capture the commit hash from the git output and pass it to `logbook_log` via the `commits` parameter (a list). Also pass `repo` and `branch`. Git metadata is stored nested under a `git` key:

```json
{"git": {"repo": "logbook", "branch": "master", "commits": ["abc1234", "def5678"]}}
```

Example flow:
1. Make changes, commit → get hash like `abc1234`
2. Log the work: `logbook_log(description="...", project_id="...", commits=["abc1234"], repo="logbook", branch="master")`

Multiple commits can be attached to a single log entry when they represent the same piece of work.

Always include commit metadata when the logged work directly corresponds to a commit. Do not include it for work that has no associated commit (planning, research, etc.).

## Configuration

All env vars are prefixed `LOGBOOK_`. Key ones:

- `LOGBOOK_HOME` — base directory for DB, .env, and project files (default `~/.logbook`). All other paths derive from this unless individually overridden.
- `LOGBOOK_DB_PATH` — database file path (default `$LOGBOOK_HOME/logbook.db`)
- `LOGBOOK_HOST`, `LOGBOOK_PORT` — server bind address (default `0.0.0.0:8000`)

The CLI and MCP server use `LOGBOOK_URL` (default `http://localhost:8000`).
