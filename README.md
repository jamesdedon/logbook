# Logbook

Local-first agentic work journal and planning tool. Runs in a container with a REST API designed for AI agent consumption. Terminal-first — no web UI needed.

## Why

When AI coding assistants accelerate your output, it becomes hard to track what got done and when. Logbook records work as it happens and helps you plan what's next.

## Features

- **Projects, goals, tasks** with priorities and dependencies
- **Work log** with timestamps and optional git metadata
- **Summary endpoints**: today, next actions, blocked tasks, weekly report
- **CLI** (`logbook`) for terminal workflows
- **MCP server** for native Claude Code integration (16 tools)
- **REST API** with clean JSON responses for any agent or script
- **SQLite** — single file, no external dependencies

## Quick Start

### Run locally

```bash
pip install -e .
LOGBOOK_DB_PATH=./logbook.db alembic upgrade head
LOGBOOK_DB_PATH=./logbook.db uvicorn logbook.main:app
```

### Run with Docker

```bash
docker compose up -d --build
```

The API is available at `http://localhost:8000`. OpenAPI docs at `/docs`.

## CLI Usage

```bash
# Log work (most common command)
logbook log "shipped the auth refactor"
logbook log "fixed deployment bug" --project <ID> --commit abc123

# Tasks
logbook tasks                          # active tasks
logbook task create <PROJECT> "title" --priority high
logbook task done <ID>

# Planning
logbook summary                        # full overview
logbook today                          # today's activity
logbook next                           # what to work on next
logbook blocked                        # blocked tasks
logbook weekly                         # weekly export report
logbook weekly -w 1                    # last week

# Projects & goals
logbook project create "my-project"
logbook goal create <PROJECT> "Ship v1" --target 2026-04-15

# All commands support --json for machine-readable output
logbook summary --json
```

## MCP Server

Register with Claude Code:

```bash
claude mcp add logbook -e LOGBOOK_URL=http://localhost:8000 -- logbook-mcp
```

This gives Claude Code 16 native tools: `logbook_summary`, `logbook_log`, `logbook_tasks`, `logbook_weekly`, etc.

## REST API

All responses use a consistent envelope:

```json
{"data": {...}, "meta": {"total": 42, "limit": 20, "offset": 0}}
```

### Endpoints

| Area | Endpoints |
|------|-----------|
| Projects | `POST/GET /projects`, `GET/PATCH/DELETE /projects/{id}` |
| Goals | `POST/GET /projects/{id}/goals`, `GET/PATCH/DELETE /goals/{id}` |
| Tasks | `POST /projects/{id}/tasks`, `GET /tasks`, `GET/PATCH/DELETE /tasks/{id}` |
| Dependencies | `POST/DELETE /tasks/{id}/dependencies` |
| Work Log | `POST/GET /log`, `GET/PATCH/DELETE /log/{id}` |
| Summary | `GET /summary`, `/summary/today`, `/summary/next`, `/summary/blocked`, `/summary/weekly` |

### Task filtering

`GET /tasks` supports: `status`, `priority`, `project_id`, `goal_id`, `blocked`, `tag`, `q` (text search), `sort`, `limit`, `offset`.

## Stack

- Python 3.12+, FastAPI, SQLAlchemy (async), SQLite via aiosqlite
- Alembic for migrations
- Typer + Rich for CLI
- MCP SDK for agent integration
