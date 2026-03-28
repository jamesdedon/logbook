# Logbook

Local-first agentic work journal and planning tool. Runs on your computer with a REST API designed for AI agent consumption. Terminal-first — no web UI needed.

## What is Logbook?

Logbook is a personal work journal that runs quietly in the background on your computer. It keeps track of what you've worked on, what you're working on now, and what's coming up next.

The key difference from a regular to-do list: Logbook is designed to work *with* your AI assistant (Claude Code). Claude can read from and write to your journal automatically, so you don't have to remember to update it yourself.

Think of it as a work diary that writes itself.

## Why would I want this?

When you work with Claude Code, things move fast. You might fix three bugs, refactor a module, and start a new feature all in one session. By the end of the week, it's hard to remember what happened on Tuesday.

Logbook solves this by:

- **Recording work as it happens.** Claude logs what it did after completing tasks, so you have a running record without doing anything.
- **Helping you plan.** You can create projects, set goals, and break work into tasks with priorities. Claude can check what's next and suggest what to work on.
- **Letting you search everything.** Can't remember where that authentication fix went? Search "auth" and Logbook finds every project, task, and log entry that mentions it.
- **Giving you weekly reports.** Need to remember what you accomplished last week? One command and you have a full summary grouped by project and day. Export it as markdown to share with your team.

## Features

- **Projects, goals, tasks** with priorities and dependencies
- **Work log** with timestamps and optional git metadata
- **Summary endpoints**: today, next actions, blocked tasks, weekly report
- **Full-text search** across all entities (FTS5 with stemming and prefix matching)
- **Markdown export** for weekly reports, filterable by project
- **CLI** (`logbook`) for terminal workflows
- **MCP server** for native Claude Code integration (18 tools)
- **REST API** with clean JSON responses for any agent or script
- **SQLite** — single file, no external dependencies

## How it works

Logbook has three parts:

1. **A server** that runs on your computer and stores everything in a small database file. Once set up, it starts automatically when your computer boots. You never need to think about it.

2. **A command-line tool** (`logbook`) that lets you interact with it from your terminal. You can log work, check your tasks, see summaries, and search.

3. **A connection to Claude Code** so that Claude can use Logbook directly. When you start a session, Claude can check what's on your plate. When you finish work, Claude can log it. You don't have to tell Claude to do this — it has the tools available and can use them naturally.

## Getting started

### Prerequisites

- Python 3.12 or newer
- Claude Code installed
- Git (to clone the project)

### Installation

```bash
git clone git@github.com:jamesdedon/logbook.git ~/projects/logbook
cd ~/projects/logbook
pip install .
```

### Start the server

**On Linux (Fedora, Ubuntu, etc.):**

```bash
mkdir -p ~/.config/systemd/user

cat > ~/.config/systemd/user/logbook.service << 'EOF'
[Unit]
Description=Logbook - agentic work journal
After=network.target

[Service]
Type=simple
WorkingDirectory=%h/projects/logbook
Environment=LOGBOOK_DB_PATH=%h/projects/logbook/logbook.db
ExecStartPre=alembic upgrade head
ExecStart=uvicorn logbook.main:app --host 0.0.0.0 --port 8000
Restart=on-failure

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now logbook
loginctl enable-linger $USER
```

**On Mac:**

```bash
LOGBOOK_DB_PATH=~/projects/logbook/logbook.db alembic upgrade head
LOGBOOK_DB_PATH=~/projects/logbook/logbook.db uvicorn logbook.main:app &
```

(For a permanent Mac setup, you can create a launchd plist — ask Claude Code to help with that.)

**With Docker/Podman:**

```bash
docker compose up -d --build
```

### Verify it's running

```bash
curl http://localhost:8000/health
```

You should see: `{"status":"ok"}`

The API is available at `http://localhost:8000`. OpenAPI docs at `/docs`.

### Connect Claude Code

Run this once:

```bash
claude mcp add logbook -s user -e LOGBOOK_URL=http://localhost:8000 -- logbook-mcp
```

That's it. Claude Code now has access to Logbook in every session.

## Daily usage

### Things you can say to Claude Code

You don't need to memorize commands. Just talk to Claude naturally:

- "What's on my plate?" — Claude checks Logbook for your active tasks and priorities.
- "Log that we finished the API refactor." — Claude creates a work log entry.
- "Create a task for fixing the login bug, high priority." — Claude adds it to your project.
- "What did I work on last week?" — Claude pulls up your weekly report.
- "Search for anything related to database migrations." — Claude searches across all your projects, tasks, and log entries.
- "Mark that task as done." — Claude updates the task status.

### Using the command line directly

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
logbook weekly                         # weekly report
logbook weekly -w 1 -p <PROJECT>       # last week, single project

# Search
logbook search "auth"                  # search everything
logbook search "database" -t task      # search only tasks

# Export
logbook export                         # markdown to stdout
logbook export -o report.md            # save to file
logbook export -p <PROJECT> -o standup.md  # single project

# Projects & goals
logbook project create "my-project"
logbook goal create <PROJECT> "Ship v1" --target 2026-04-15

# All commands support --json for machine-readable output
logbook summary --json
```

### How information is organized

- **Projects** are the top level. You might have one for each repo, initiative, or area of work.
- **Goals** are milestones within a project — things like "Ship v1" or "Migrate to new database."
- **Tasks** are concrete work items. They have priorities (low, medium, high, critical) and can depend on each other (Task B can't start until Task A is done).
- **Log entries** are timestamped records of work done. They can be linked to a project and task, or standalone.

Everything is searchable.

## Concepts

### What does "blocked" mean?

A task is blocked when it depends on another task that isn't finished yet. For example, you can't deploy code before the tests pass. Logbook tracks these dependencies so Claude (and you) can focus on work that's actually actionable right now.

### What does "next" do?

The "next" command shows you the most impactful things to work on right now. It considers:

1. Priority — critical and high-priority tasks come first.
2. Impact — tasks that unblock other tasks are ranked higher.
3. Age — older tasks get a slight boost so nothing sits forever.

It only shows tasks that aren't blocked, so everything it suggests is something you can actually start.

### Where is my data?

Everything is stored in a single file called `logbook.db` in your project directory. It's a standard SQLite database. Your data never leaves your computer — there's no cloud service, no account, no sync. If you want to back it up, just copy that file.

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
| Export | `GET /summary/export/weekly` |
| Search | `GET /search?q=keyword` |

### Task filtering

`GET /tasks` supports: `status`, `priority`, `project_id`, `goal_id`, `blocked`, `tag`, `q` (text search), `sort`, `limit`, `offset`.

## Updating

When new features are added:

```bash
cd ~/projects/logbook
git pull
pip install .
systemctl --user restart logbook    # Linux
```

Database changes are applied automatically on restart.

## Stack

- Python 3.12+, FastAPI, SQLAlchemy (async), SQLite via aiosqlite
- Alembic for migrations
- Typer + Rich for CLI
- MCP SDK for agent integration
