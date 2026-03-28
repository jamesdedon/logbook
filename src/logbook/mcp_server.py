"""MCP server for logbook. Calls the REST API so it works with a running logbook instance."""

import json
import os

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("logbook", instructions=(
    "Logbook is a local work journal and planning tool. "
    "Use these tools to log work, manage tasks, and check what's next. "
    "Log work as you complete it. Check 'summary' or 'next' at session start."
))

BASE_URL = os.environ.get("LOGBOOK_URL", "http://localhost:8000")


def _get(path: str, params: dict | None = None) -> dict:
    with httpx.Client(base_url=BASE_URL, timeout=10) as c:
        resp = c.get(path, params=params)
        resp.raise_for_status()
        return resp.json()


def _post(path: str, body: dict) -> dict:
    with httpx.Client(base_url=BASE_URL, timeout=10) as c:
        resp = c.post(path, json=body)
        resp.raise_for_status()
        return resp.json()


def _patch(path: str, body: dict) -> dict:
    with httpx.Client(base_url=BASE_URL, timeout=10) as c:
        resp = c.patch(path, json=body)
        resp.raise_for_status()
        return resp.json()


# --- Summary / Planning tools ---

@mcp.tool()
def logbook_summary() -> str:
    """Get a full overview: active projects, task counts, blocked items, and next actions."""
    data = _get("/summary")["data"]
    lines = []
    for p in data.get("active_projects", []):
        ts = p["tasks_summary"]
        lines.append(f"Project: {p['name']} — {p['goals_active']} goals, "
                     f"{ts['todo']} todo, {ts['in_progress']} active, {ts['done']} done, "
                     f"{p['blocked_tasks']} blocked")
    if data.get("next_actions"):
        lines.append("\nNext up:")
        for n in data["next_actions"]:
            lines.append(f"  [{n['priority']}] {n['title']} (project: {n['project_name']}, id: {n['id']})")
    if data.get("blocked_tasks"):
        lines.append("\nBlocked:")
        for bt in data["blocked_tasks"]:
            blockers = ", ".join(b["title"] for b in bt["blocked_by"])
            lines.append(f"  {bt['title']} — waiting on: {blockers}")
    return "\n".join(lines) if lines else "No active projects."


@mcp.tool()
def logbook_weekly(weeks_back: int = 0) -> str:
    """Get a weekly export report showing all work done, grouped by project and day.

    Args:
        weeks_back: 0 for current week, 1 for last week, 2 for two weeks ago, etc.
    """
    data = _get("/summary/weekly", params={"weeks_back": weeks_back})["data"]
    lines = [f"Weekly Report ({data['week_start'][:10]} → {data['week_end'][:10]})"]
    lines.append(f"  {data['total_log_entries']} entries | "
                 f"{data['total_tasks_completed']} tasks completed | "
                 f"{data['total_tasks_created']} tasks created | "
                 f"{data['total_goals_completed']} goals completed")

    if data.get("by_project"):
        lines.append("\nBy project:")
        for p in data["by_project"]:
            lines.append(f"  {p['project_name']} — {p['entry_count']} entries")
            for e in p["entries"]:
                day = e["created_at"][:10]
                lines.append(f"    {day} — {e['description']}")

    if data.get("tasks_completed"):
        lines.append("\nTasks completed:")
        for t in data["tasks_completed"]:
            lines.append(f"  ✓ {t['title']}")

    if not data.get("by_project") and not data.get("tasks_completed"):
        lines.append("  No activity this week.")

    return "\n".join(lines)


@mcp.tool()
def logbook_today() -> str:
    """See what work was logged today and which tasks were completed."""
    data = _get("/summary/today")["data"]
    lines = []
    if data.get("log_entries"):
        lines.append("Work logged today:")
        for e in data["log_entries"]:
            time = e["created_at"][11:16] if len(e["created_at"]) > 16 else ""
            lines.append(f"  {time} — {e['description']}")
    if data.get("tasks_completed"):
        lines.append("\nTasks completed today:")
        for t in data["tasks_completed"]:
            lines.append(f"  ✓ {t['title']}")
    return "\n".join(lines) if lines else "No activity logged today."


@mcp.tool()
def logbook_next() -> str:
    """Get the next recommended actions, sorted by priority and impact."""
    data = _get("/summary/next")["data"]
    if not data.get("tasks"):
        return "Nothing queued up."
    lines = ["Next actions:"]
    for t in data["tasks"]:
        lines.append(f"  [{t['priority']}] {t['title']} (project: {t['project_name']}, id: {t['id']})")
    return "\n".join(lines)


@mcp.tool()
def logbook_blocked() -> str:
    """List all blocked tasks and what's blocking them."""
    data = _get("/summary/blocked")["data"]
    if not data:
        return "No blocked tasks."
    lines = ["Blocked tasks:"]
    for bt in data:
        blockers = ", ".join(f"{b['title']} ({b['status']})" for b in bt["blocked_by"])
        lines.append(f"  {bt['title']} — waiting on: {blockers}")
    return "\n".join(lines)


# --- Work Log tools ---

@mcp.tool()
def logbook_log(
    description: str,
    project_id: str | None = None,
    task_id: str | None = None,
    commit: str | None = None,
    repo: str | None = None,
    branch: str | None = None,
) -> str:
    """Log a work entry. Use this after completing work to record what was done.

    Args:
        description: What was done (be specific and concise)
        project_id: Optional project ID to link this entry to
        task_id: Optional task ID to link this entry to
        commit: Optional git commit hash
        repo: Optional repository name
        branch: Optional git branch name
    """
    body: dict = {"description": description}
    if project_id:
        body["project_id"] = project_id
    if task_id:
        body["task_id"] = task_id
    metadata = {}
    if commit:
        metadata["commit"] = commit
    if repo:
        metadata["repo"] = repo
    if branch:
        metadata["branch"] = branch
    if metadata:
        body["metadata"] = metadata

    data = _post("/log", body)["data"]
    return f"Logged: {data['description']} (id: {data['id']})"


@mcp.tool()
def logbook_log_list(
    project_id: str | None = None,
    task_id: str | None = None,
    since: str | None = None,
    limit: int = 10,
) -> str:
    """List recent work log entries.

    Args:
        project_id: Filter by project ID
        task_id: Filter by task ID
        since: ISO-8601 datetime to filter entries from (e.g. '2026-03-28T00:00:00')
        limit: Max entries to return (default 10)
    """
    params: dict = {"limit": limit}
    if project_id:
        params["project_id"] = project_id
    if task_id:
        params["task_id"] = task_id
    if since:
        params["since"] = since

    data = _get("/log", params)
    entries = data["data"]
    if not entries:
        return "No log entries found."
    lines = []
    for e in entries:
        time = e["created_at"][11:16] if len(e["created_at"]) > 16 else ""
        project_note = f" [project: {e['project_id'][:12]}]" if e.get("project_id") else ""
        lines.append(f"  {time} — {e['description']}{project_note}")
    return "\n".join(lines)


# --- Project tools ---

@mcp.tool()
def logbook_projects() -> str:
    """List all active projects."""
    data = _get("/projects")
    projects = data["data"]
    if not projects:
        return "No active projects."
    lines = []
    for p in projects:
        lines.append(f"  {p['name']} (id: {p['id']}, status: {p['status']})")
    return "\n".join(lines)


@mcp.tool()
def logbook_project_create(name: str, description: str = "") -> str:
    """Create a new project.

    Args:
        name: Project name
        description: Optional project description
    """
    data = _post("/projects", {"name": name, "description": description})["data"]
    return f"Created project: {data['name']} (id: {data['id']})"


@mcp.tool()
def logbook_project_detail(project_id: str) -> str:
    """Get detailed info about a project including task counts.

    Args:
        project_id: The project ID
    """
    data = _get(f"/projects/{project_id}")["data"]
    counts = data.get("counts", {})
    return (f"Project: {data['name']} ({data['status']})\n"
            f"  {data.get('description', '')}\n"
            f"  Goals: {counts.get('goals', 0)}\n"
            f"  Tasks: {counts.get('tasks_todo', 0)} todo, {counts.get('tasks_in_progress', 0)} active, "
            f"{counts.get('tasks_done', 0)} done")


# --- Task tools ---

@mcp.tool()
def logbook_tasks(
    project_id: str | None = None,
    status: str = "todo,in_progress",
    priority: str | None = None,
    blocked: bool | None = None,
    limit: int = 20,
) -> str:
    """List tasks with optional filters.

    Args:
        project_id: Filter by project ID
        status: Comma-separated statuses (default: 'todo,in_progress')
        priority: Filter by priority (low, medium, high, critical)
        blocked: If true, show only blocked tasks; if false, only unblocked
        limit: Max tasks to return
    """
    params: dict = {"status": status, "limit": limit}
    if project_id:
        params["project_id"] = project_id
    if priority:
        params["priority"] = priority
    if blocked is not None:
        params["blocked"] = str(blocked).lower()

    data = _get("/tasks", params)
    tasks = data["data"]
    if not tasks:
        return "No tasks found."
    lines = []
    for t in tasks:
        lines.append(f"  [{t['priority']}] {t['title']} — {t['status']} (id: {t['id']})")
    return "\n".join(lines)


@mcp.tool()
def logbook_task_create(
    project_id: str,
    title: str,
    description: str = "",
    priority: str = "medium",
    goal_id: str | None = None,
    blocked_by: list[str] | None = None,
) -> str:
    """Create a new task.

    Args:
        project_id: Project ID this task belongs to
        title: Task title
        description: Task description
        priority: Priority level (low, medium, high, critical)
        goal_id: Optional goal ID to link this task to
        blocked_by: Optional list of task IDs that block this task
    """
    body: dict = {"title": title, "description": description, "priority": priority}
    if goal_id:
        body["goal_id"] = goal_id
    if blocked_by:
        body["blocked_by"] = blocked_by

    data = _post(f"/projects/{project_id}/tasks", body)["data"]
    return f"Created task: {data['title']} (id: {data['id']}, priority: {data['priority']})"


@mcp.tool()
def logbook_task_update(
    task_id: str,
    status: str | None = None,
    title: str | None = None,
    priority: str | None = None,
) -> str:
    """Update a task's status, title, or priority. Use status='done' to complete a task.

    Args:
        task_id: The task ID to update
        status: New status (todo, in_progress, done, cancelled)
        title: New title
        priority: New priority (low, medium, high, critical)
    """
    body = {}
    if status:
        body["status"] = status
    if title:
        body["title"] = title
    if priority:
        body["priority"] = priority

    data = _patch(f"/tasks/{task_id}", body)["data"]
    return f"Updated task: {data['title']} — {data['status']} (priority: {data['priority']})"


@mcp.tool()
def logbook_task_detail(task_id: str) -> str:
    """Get full detail on a task including dependencies and recent log entries.

    Args:
        task_id: The task ID
    """
    data = _get(f"/tasks/{task_id}")["data"]
    lines = [f"Task: {data['title']} [{data['status']}] (priority: {data['priority']})"]
    if data.get("description"):
        lines.append(f"  {data['description']}")
    if data.get("is_blocked"):
        lines.append("  STATUS: BLOCKED")
    if data.get("blocked_by"):
        lines.append("  Blocked by:")
        for b in data["blocked_by"]:
            lines.append(f"    - {b['title']} ({b['status']})")
    if data.get("blocks"):
        lines.append("  Blocks:")
        for b in data["blocks"]:
            lines.append(f"    - {b['title']} ({b['status']})")
    if data.get("recent_log_entries"):
        lines.append("  Recent work:")
        for e in data["recent_log_entries"]:
            lines.append(f"    - {e['description']}")
    return "\n".join(lines)


# --- Goal tools ---

@mcp.tool()
def logbook_goal_create(
    project_id: str,
    title: str,
    description: str = "",
    target_date: str | None = None,
) -> str:
    """Create a new goal/milestone within a project.

    Args:
        project_id: Project ID
        title: Goal title
        description: Goal description
        target_date: Optional target date (YYYY-MM-DD)
    """
    body: dict = {"title": title, "description": description}
    if target_date:
        body["target_date"] = target_date
    data = _post(f"/projects/{project_id}/goals", body)["data"]
    return f"Created goal: {data['title']} (id: {data['id']})"


@mcp.tool()
def logbook_goals(project_id: str) -> str:
    """List goals for a project.

    Args:
        project_id: Project ID
    """
    data = _get(f"/projects/{project_id}/goals")
    goals = data["data"]
    if not goals:
        return "No active goals."
    lines = []
    for g in goals:
        target = f" (target: {g['target_date']})" if g.get("target_date") else ""
        lines.append(f"  {g['title']} — {g['status']}{target} (id: {g['id']})")
    return "\n".join(lines)


# --- Search ---

@mcp.tool()
def logbook_search(
    query: str,
    type: str | None = None,
    limit: int = 20,
) -> str:
    """Search across all projects, goals, tasks, and work log entries using keywords.

    Supports prefix matching (auto-applied), phrase matching ("exact phrase"),
    and porter stemming (e.g. "running" matches "run").

    Args:
        query: Search keywords
        type: Optional filter by entity type (comma-separated: project,goal,task,work_log_entry)
        limit: Max results (default 20)
    """
    params: dict = {"q": query, "limit": limit}
    if type:
        params["type"] = type

    data = _get("/search", params)["data"]
    results = data["results"]
    if not results:
        return f"No results for '{query}'."

    lines = [f"Search results for '{query}' ({data['total']} matches):"]
    for r in results:
        label = r["entity_type"].replace("_", " ")
        lines.append(f"  [{label}] {r['title_snippet']} (id: {r['entity_id']})")
        if r["body_snippet"].strip():
            lines.append(f"    {r['body_snippet']}")
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
