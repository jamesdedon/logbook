import json
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from logbook.config import settings
from logbook.services.summary import get_weekly_report


def _to_local(iso_str: str) -> datetime:
    """Convert an ISO-8601 UTC timestamp to a local datetime."""
    dt = datetime.fromisoformat(iso_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(settings.tz)


def _utc_to_local_time(iso_str: str) -> str:
    """Convert an ISO-8601 UTC timestamp to local HH:MM."""
    try:
        return _to_local(iso_str).strftime("%H:%M")
    except (ValueError, TypeError):
        return iso_str[11:16] if len(iso_str) > 16 else ""


def _utc_to_local_date(iso_str: str) -> str:
    """Convert an ISO-8601 UTC timestamp to local YYYY-MM-DD."""
    try:
        return _to_local(iso_str).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return iso_str[:10]


def _render_weekly_markdown(data: dict) -> str:
    """Render a weekly report as markdown."""
    week_start = data["week_start"][:10]
    week_end = data["week_end"][:10]

    lines = [
        f"# Weekly Report: {week_start} to {week_end}",
        "",
        f"**Log entries:** {data['total_log_entries']}  ",
        f"**Tasks completed:** {data['total_tasks_completed']}  ",
        f"**Tasks created:** {data['total_tasks_created']}  ",
        f"**Goals completed:** {data['total_goals_completed']}",
        "",
    ]

    # By project
    if data["by_project"]:
        lines.append("## Work by Project")
        lines.append("")
        for pid, entries in data["by_project"].items():
            project_name = data["project_names"].get(pid, "Unknown")
            lines.append(f"### {project_name}")
            lines.append("")
            for entry in entries:
                day = _utc_to_local_date(entry.created_at)
                time = _utc_to_local_time(entry.created_at)
                meta = json.loads(entry.metadata_json) if entry.metadata_json else {}
                commit_note = ""
                git = meta.get("git", {})
                # Support both new nested format and legacy flat format
                commits = git.get("commits", [])
                if not commits and meta.get("commit"):
                    commits = [meta["commit"]]
                repo = git.get("repo") or meta.get("repo")
                if commits:
                    short = ", ".join(f"`{c[:7]}`" for c in commits)
                    commit_note = f" ({short}"
                    if repo:
                        commit_note += f" in {repo}"
                    commit_note += ")"
                lines.append(f"- **{day}** {time} — {entry.description}{commit_note}")
            lines.append("")

    # By day (regroup using local dates)
    all_entries = [e for entries in data["days"].values() for e in entries]
    if all_entries:
        local_days: dict[str, list] = {}
        for entry in all_entries:
            local_day = _utc_to_local_date(entry.created_at)
            local_days.setdefault(local_day, []).append(entry)
        lines.append("## Daily Breakdown")
        lines.append("")
        for day, entries in sorted(local_days.items()):
            weekday = datetime.fromisoformat(day).strftime("%A")
            lines.append(f"### {weekday}, {day}")
            lines.append("")
            for entry in entries:
                time = _utc_to_local_time(entry.created_at)
                lines.append(f"- {time} — {entry.description}")
            lines.append("")

    # Tasks completed (grouped by project)
    if data["tasks_completed"]:
        lines.append("## Tasks Completed")
        lines.append("")
        completed_by_project: dict[str, list] = {}
        for task in data["tasks_completed"]:
            pid = task.project_id or "unlinked"
            completed_by_project.setdefault(pid, []).append(task)
        for pid, tasks in completed_by_project.items():
            pname = data["project_names"].get(pid, "Unknown")
            lines.append(f"### {pname}")
            lines.append("")
            for task in tasks:
                completed = task.completed_at[:10] if task.completed_at else ""
                lines.append(f"- [x] {task.title} ({task.priority}) — completed {completed}")
            lines.append("")

    # Tasks created (grouped by project)
    if data["tasks_created"]:
        lines.append("## Tasks Created")
        lines.append("")
        created_by_project: dict[str, list] = {}
        for task in data["tasks_created"]:
            pid = task.project_id or "unlinked"
            created_by_project.setdefault(pid, []).append(task)
        for pid, tasks in created_by_project.items():
            pname = data["project_names"].get(pid, "Unknown")
            lines.append(f"### {pname}")
            lines.append("")
            for task in tasks:
                status_marker = "x" if task.status == "done" else " "
                lines.append(f"- [{status_marker}] {task.title} ({task.priority}) — {task.status}")
            lines.append("")

    # Goals completed
    if data["goals_completed"]:
        lines.append("## Goals Completed")
        lines.append("")
        for goal in data["goals_completed"]:
            lines.append(f"- {goal.title}")
        lines.append("")

    # Footer
    now = datetime.now(settings.tz).strftime("%Y-%m-%d %H:%M %Z")
    lines.append("---")
    lines.append(f"*Generated by Logbook on {now}*")
    lines.append("")

    return "\n".join(lines)


async def export_weekly_markdown(db: AsyncSession, weeks_back: int = 0, project_id: str | None = None) -> str:
    data = await get_weekly_report(db, weeks_back=weeks_back, project_id=project_id)
    return _render_weekly_markdown(data)
