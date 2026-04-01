"""MCP server for logbook. Calls the REST API so it works with a running logbook instance."""

import json
import os
import textwrap
from datetime import datetime, timezone

import httpx
from mcp.server.fastmcp import FastMCP

from logbook.config import settings

WRAP_WIDTH = 100


def _wrap(text: str, indent: str = "  ") -> str:
    """Wrap text so that continuation lines stay indented after a line break."""
    return textwrap.fill(
        text, width=WRAP_WIDTH, initial_indent=indent, subsequent_indent=indent,
    )


def _to_local_time(iso_str: str) -> str:
    """Convert an ISO-8601 UTC timestamp to local HH:MM."""
    try:
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        local_dt = dt.astimezone(settings.tz)
        return local_dt.strftime("%H:%M")
    except (ValueError, TypeError):
        return iso_str[11:16] if len(iso_str) > 16 else ""

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


def _delete(path: str) -> dict:
    with httpx.Client(base_url=BASE_URL, timeout=10) as c:
        resp = c.delete(path)
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
        if p.get("motivation"):
            lines.append(_wrap(f"Motivation: {p['motivation']}"))
    if data.get("next_actions"):
        lines.append("\nNext up:")
        for n in data["next_actions"]:
            lines.append(_wrap(f"[{n['priority']}] {n['title']} (project: {n['project_name']}, id: {n['id']})"))
            if n.get("rationale"):
                lines.append(_wrap(f"Why: {n['rationale']}", indent="    "))
    if data.get("blocked_tasks"):
        lines.append("\nBlocked:")
        for bt in data["blocked_tasks"]:
            blockers = ", ".join(b["title"] for b in bt["blocked_by"])
            lines.append(_wrap(f"{bt['title']} — waiting on: {blockers}"))
    return "\n".join(lines) if lines else "No active projects."


@mcp.tool()
def logbook_weekly(weeks_back: int = 0, project_id: str | None = None) -> str:
    """Get a weekly export report showing all work done, grouped by project and day.

    Args:
        weeks_back: 0 for current week, 1 for last week, 2 for two weeks ago, etc.
        project_id: Optional project ID to filter the report to a single project
    """
    params: dict = {"weeks_back": weeks_back}
    if project_id:
        params["project_id"] = project_id
    data = _get("/summary/weekly", params=params)["data"]
    lines = [f"Weekly Report ({data['week_start'][:10]} → {data['week_end'][:10]})"]
    lines.append(_wrap(f"{data['total_log_entries']} entries | "
                       f"{data['total_tasks_completed']} tasks completed | "
                       f"{data['total_tasks_created']} tasks created | "
                       f"{data['total_goals_completed']} goals completed"))

    if data.get("by_project"):
        lines.append("\nBy project:")
        for p in data["by_project"]:
            lines.append(_wrap(f"{p['project_name']} — {p['entry_count']} entries"))
            if p.get("project_motivation"):
                lines.append(_wrap(f"Motivation: {p['project_motivation']}", indent="    "))
            for e in p["entries"]:
                day = e["created_at"][:10]
                lines.append(_wrap(f"{day} — {e['description']}", indent="    "))

    if data.get("tasks_completed"):
        lines.append("\nTasks completed:")
        by_proj: dict[str, list] = {}
        for t in data["tasks_completed"]:
            pname = t.get("project_name", "Unknown")
            by_proj.setdefault(pname, []).append(t)
        for pname, tasks in by_proj.items():
            lines.append(_wrap(pname))
            for t in tasks:
                lines.append(_wrap(f"✓ {t['title']}", indent="    "))

    if not data.get("by_project") and not data.get("tasks_completed"):
        lines.append(_wrap("No activity this week."))

    return "\n".join(lines)


@mcp.tool()
def logbook_today() -> str:
    """See what work was logged today and which tasks were completed."""
    data = _get("/summary/today")["data"]
    lines = []
    if data.get("log_entries"):
        lines.append("Work logged today:")
        for e in data["log_entries"]:
            time = _to_local_time(e["created_at"])
            lines.append(_wrap(f"{time} — {e['description']}"))
    if data.get("tasks_completed"):
        lines.append("\nTasks completed today:")
        by_proj: dict[str, list] = {}
        for t in data["tasks_completed"]:
            pname = t.get("project_name", "Unknown")
            by_proj.setdefault(pname, []).append(t)
        for pname, tasks in by_proj.items():
            lines.append(_wrap(pname))
            for t in tasks:
                lines.append(_wrap(f"✓ {t['title']}", indent="    "))
    return "\n".join(lines) if lines else "No activity logged today."


@mcp.tool()
def logbook_next() -> str:
    """Get the next recommended actions, sorted by priority and impact."""
    data = _get("/summary/next")["data"]
    if not data.get("tasks"):
        return "Nothing queued up."
    lines = ["Next actions:"]
    for t in data["tasks"]:
        lines.append(_wrap(f"[{t['priority']}] {t['title']} (project: {t['project_name']}, id: {t['id']})"))
        if t.get("rationale"):
            lines.append(_wrap(f"Why: {t['rationale']}", indent="    "))
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
        lines.append(_wrap(f"{bt['title']} — waiting on: {blockers}"))
    return "\n".join(lines)


# --- Work Log tools ---

@mcp.tool()
def logbook_log(
    description: str,
    project_id: str | None = None,
    task_id: str | None = None,
    commits: list[str] | None = None,
    repo: str | None = None,
    branch: str | None = None,
) -> str:
    """Log a work entry. Use this after completing work to record what was done.

    Args:
        description: What was done (be specific and concise)
        project_id: Optional project ID to link this entry to
        task_id: Optional task ID to link this entry to
        commits: Optional list of git commit hashes associated with this work
        repo: Optional repository name
        branch: Optional git branch name
    """
    body: dict = {"description": description}
    if project_id:
        body["project_id"] = project_id
    if task_id:
        body["task_id"] = task_id
    if commits or repo or branch:
        git_info: dict = {}
        if repo:
            git_info["repo"] = repo
        if branch:
            git_info["branch"] = branch
        if commits:
            git_info["commits"] = commits
        body["metadata"] = {"git": git_info}

    data = _post("/log", body)["data"]
    return f"Logged: {data['description']} (id: {data['id']})"


@mcp.tool()
def logbook_log_update(
    entry_id: str,
    description: str | None = None,
    project_id: str | None = None,
    task_id: str | None = None,
) -> str:
    """Update an existing work log entry.

    Args:
        entry_id: The ID of the log entry to update
        description: New description text
        project_id: New project ID to link to
        task_id: New task ID to link to
    """
    body: dict = {}
    if description is not None:
        body["description"] = description
    if project_id is not None:
        body["project_id"] = project_id
    if task_id is not None:
        body["task_id"] = task_id
    if not body:
        return "Nothing to update — provide at least one field."
    data = _patch(f"/log/{entry_id}", body)["data"]
    return f"Updated log entry {data['id']}: {data['description']}"


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
        time = _to_local_time(e["created_at"])
        project_note = f" [project: {e['project_id'][:12]}]" if e.get("project_id") else ""
        lines.append(_wrap(f"{time} — {e['description']}{project_note}"))
    return "\n".join(lines)


@mcp.tool()
def logbook_log_delete(entry_id: str) -> str:
    """Delete a work log entry.

    Args:
        entry_id: The ID of the log entry to delete
    """
    _delete(f"/log/{entry_id}")
    return f"Deleted log entry {entry_id}."


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
        lines.append(_wrap(f"{p['name']} (id: {p['id']}, status: {p['status']})"))
    return "\n".join(lines)


@mcp.tool()
def logbook_project_create(name: str, description: str = "", motivation: str = "") -> str:
    """Create a new project.

    Args:
        name: Project name
        description: Optional project description
        motivation: Why does this project exist? What problem does it solve?
    """
    data = _post("/projects", {"name": name, "description": description, "motivation": motivation})["data"]
    result = f"Created project: {data['name']} (id: {data['id']})"
    if not motivation:
        result += "\n\n→ No motivation provided. Why does this project exist? Call logbook_project_detail to update, or recreate with motivation= to record it."
    return result


@mcp.tool()
def logbook_project_detail(project_id: str) -> str:
    """Get detailed info about a project including task counts.

    Args:
        project_id: The project ID
    """
    data = _get(f"/projects/{project_id}")["data"]
    motivation = data.get("motivation", "")
    counts = data.get("counts", {})
    lines = [f"Project: {data['name']} ({data['status']})"]
    if data.get("description"):
        lines.append(_wrap(data['description']))
    if motivation:
        lines.append(_wrap(f"Motivation: {motivation}"))
    lines.append(_wrap(f"Goals: {counts.get('goals', 0)}"))
    lines.append(_wrap(f"Tasks: {counts.get('tasks_todo', 0)} todo, {counts.get('tasks_in_progress', 0)} active, "
                       f"{counts.get('tasks_done', 0)} done"))
    return "\n".join(lines)


@mcp.tool()
def logbook_project_update(
    project_id: str,
    name: str | None = None,
    description: str | None = None,
    motivation: str | None = None,
    status: str | None = None,
) -> str:
    """Update a project's name, description, motivation, or status.

    Args:
        project_id: The project ID to update
        name: New project name
        description: New project description
        motivation: New motivation text
        status: New status (active, archived)
    """
    body: dict = {}
    if name is not None:
        body["name"] = name
    if description is not None:
        body["description"] = description
    if motivation is not None:
        body["motivation"] = motivation
    if status is not None:
        body["status"] = status
    if not body:
        return "Nothing to update — provide at least one field."
    data = _patch(f"/projects/{project_id}", body)["data"]
    return f"Updated project: {data['name']} (id: {data['id']}, status: {data['status']})"


@mcp.tool()
def logbook_project_delete(project_id: str) -> str:
    """Permanently delete a project and all its goals and tasks. This cannot be undone.

    Args:
        project_id: The project ID to delete
    """
    _delete(f"/projects/{project_id}")
    return f"Deleted project {project_id}."


@mcp.tool()
def logbook_project_archive(project_id: str) -> str:
    """Archive a project. Archived projects are hidden from the default project list and summary.

    Args:
        project_id: The project ID to archive
    """
    data = _patch(f"/projects/{project_id}", {"status": "archived"})["data"]
    return f"Archived project: {data['name']} (id: {data['id']})"


@mcp.tool()
def logbook_project_unarchive(project_id: str) -> str:
    """Unarchive a project, restoring it to active status.

    Args:
        project_id: The project ID to unarchive
    """
    data = _patch(f"/projects/{project_id}", {"status": "active"})["data"]
    return f"Unarchived project: {data['name']} (id: {data['id']})"


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
        pname = t.get("project_name", "")
        lines.append(_wrap(f"[{t['priority']}] {t['title']} — {t['status']} (id: {t['id']}, project: {pname})"))
    return "\n".join(lines)


@mcp.tool()
def logbook_task_create(
    project_id: str,
    title: str,
    description: str = "",
    rationale: str = "",
    notes: str = "",
    priority: str = "medium",
    goal_id: str | None = None,
    blocked_by: list[str] | None = None,
) -> str:
    """Create a new task.

    Args:
        project_id: Project ID this task belongs to
        title: Task title
        description: Task description
        rationale: Why is this task needed? What triggered it?
        notes: Additional context, findings, or running commentary on this task
        priority: Priority level (low, medium, high, critical)
        goal_id: Optional goal ID to link this task to
        blocked_by: Optional list of task IDs that block this task
    """
    body: dict = {"title": title, "description": description, "rationale": rationale, "notes": notes, "priority": priority}
    if goal_id:
        body["goal_id"] = goal_id
    if blocked_by:
        body["blocked_by"] = blocked_by

    data = _post(f"/projects/{project_id}/tasks", body)["data"]
    result = f"Created task: {data['title']} (id: {data['id']}, priority: {data['priority']})"
    if not rationale:
        result += "\n\n→ No rationale provided. Why is this task needed? What triggered it?"
    return result


@mcp.tool()
def logbook_task_update(
    task_id: str,
    status: str | None = None,
    title: str | None = None,
    description: str | None = None,
    notes: str | None = None,
    priority: str | None = None,
) -> str:
    """Update a task's status, title, description, notes, or priority. Use status='done' to complete a task.

    Args:
        task_id: The task ID to update
        status: New status (todo, in_progress, done, cancelled)
        title: New title
        description: New description
        notes: Additional context, findings, or running commentary on this task
        priority: New priority (low, medium, high, critical)
    """
    body = {}
    if status:
        body["status"] = status
    if title:
        body["title"] = title
    if description:
        body["description"] = description
    if notes:
        body["notes"] = notes
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
    pname = data.get("project_name", "")
    lines = [f"Task: {data['title']} [{data['status']}] (priority: {data['priority']}, project: {pname})"]
    if data.get("description"):
        lines.append(_wrap(data['description']))
    if data.get("rationale"):
        lines.append(_wrap(f"Rationale: {data['rationale']}"))
    if data.get("notes"):
        lines.append(_wrap(f"Notes: {data['notes']}"))
    if data.get("is_blocked"):
        lines.append("  STATUS: BLOCKED")
    if data.get("blocked_by"):
        lines.append("  Blocked by:")
        for b in data["blocked_by"]:
            lines.append(_wrap(f"- {b['title']} ({b['status']})", indent="    "))
    if data.get("blocks"):
        lines.append("  Blocks:")
        for b in data["blocks"]:
            lines.append(_wrap(f"- {b['title']} ({b['status']})", indent="    "))
    if data.get("recent_log_entries"):
        lines.append("  Recent work:")
        for e in data["recent_log_entries"]:
            lines.append(_wrap(f"- {e['description']}", indent="    "))
    return "\n".join(lines)


# --- Goal tools ---

@mcp.tool()
def logbook_goal_create(
    project_id: str,
    title: str,
    description: str = "",
    motivation: str = "",
    target_date: str | None = None,
) -> str:
    """Create a new goal/milestone within a project.

    Args:
        project_id: Project ID
        title: Goal title
        description: Goal description
        motivation: Why is this goal important? What does success look like?
        target_date: Optional target date (YYYY-MM-DD)
    """
    body: dict = {"title": title, "description": description, "motivation": motivation}
    if target_date:
        body["target_date"] = target_date
    data = _post(f"/projects/{project_id}/goals", body)["data"]
    result = f"Created goal: {data['title']} (id: {data['id']})"
    if not motivation:
        result += "\n\n→ No motivation provided. Why is this goal important? What does achieving it unlock?"
    return result


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
        lines.append(_wrap(f"{g['title']} — {g['status']}{target} (id: {g['id']})"))
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
        lines.append(_wrap(f"[{label}] {r['title_snippet']} (id: {r['entity_id']})"))
        if r["body_snippet"].strip():
            lines.append(_wrap(r['body_snippet'], indent="    "))
    return "\n".join(lines)


# --- Export ---

@mcp.tool()
def logbook_export_weekly(weeks_back: int = 0, project_id: str | None = None) -> str:
    """Export a weekly report as formatted markdown. Useful for sharing with teammates or saving to a file.

    Args:
        weeks_back: 0 for current week, 1 for last week, etc.
        project_id: Optional project ID to filter the report to a single project
    """
    params: dict = {"weeks_back": weeks_back}
    if project_id:
        params["project_id"] = project_id
    with httpx.Client(base_url=BASE_URL, timeout=10) as c:
        resp = c.get("/summary/export/weekly", params=params)
        resp.raise_for_status()
        return resp.text


def main():
    from setproctitle import setproctitle
    setproctitle("logbook-mcp")
    mcp.run()


if __name__ == "__main__":
    main()
