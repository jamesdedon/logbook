import json
import os
import sys

import httpx
import typer
from rich.console import Console
from rich.padding import Padding
from rich.table import Table

app = typer.Typer(name="logbook", help="Local-first agentic work journal and planning tool")
console = Console()

BASE_URL = os.environ.get("LOGBOOK_URL", "http://localhost:8000")


def _client() -> httpx.Client:
    return httpx.Client(base_url=BASE_URL, timeout=10)


def _handle_error(resp: httpx.Response):
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        console.print(f"[red]Error ({resp.status_code}):[/red] {detail}")
        raise typer.Exit(1)


def _indent(text, left: int = 2):
    """Print text with left padding that persists across line wraps."""
    console.print(Padding(text, (0, 0, 0, left)))


def _json_or_table(data, json_flag: bool, table_fn):
    if json_flag:
        console.print_json(json.dumps(data))
    else:
        table_fn(data)


# --- Projects ---

projects_app = typer.Typer(help="Manage projects")
app.add_typer(projects_app, name="projects")


@projects_app.callback(invoke_without_command=True)
def list_projects(
    ctx: typer.Context,
    all: bool = typer.Option(False, "--all", help="Include archived"),
    json_out: bool = typer.Option(False, "--json", help="JSON output"),
):
    if ctx.invoked_subcommand is not None:
        return
    with _client() as c:
        params = {"status": "archived"} if all else {}
        resp = c.get("/projects", params=params)
        _handle_error(resp)
        data = resp.json()

    def show(d):
        table = Table(title="Projects")
        table.add_column("ID", style="dim", max_width=12)
        table.add_column("Name", style="bold")
        table.add_column("Status")
        for p in d["data"]:
            table.add_row(p["id"][:12], p["name"], p["status"])
        console.print(table)

    _json_or_table(data, json_out, show)


# --- Project (singular) subcommands ---

project_app = typer.Typer(help="Project operations")
app.add_typer(project_app, name="project")


@project_app.command("create")
def project_create(
    name: str = typer.Argument(...),
    desc: str = typer.Option("", "--desc"),
    motivation: str = typer.Option("", "--motivation", "-m", help="Why does this project exist?"),
    json_out: bool = typer.Option(False, "--json"),
):
    with _client() as c:
        resp = c.post("/projects", json={"name": name, "description": desc, "motivation": motivation})
        _handle_error(resp)
        data = resp.json()["data"]

    if json_out:
        console.print_json(json.dumps(data))
    else:
        console.print(f"[green]Created project:[/green] {data['name']} ({data['id'][:12]})")


@project_app.command("show")
def project_show(
    id: str = typer.Argument(...),
    json_out: bool = typer.Option(False, "--json"),
):
    with _client() as c:
        resp = c.get(f"/projects/{id}")
        _handle_error(resp)
        data = resp.json()["data"]

    if json_out:
        console.print_json(json.dumps(data))
    else:
        console.print(f"[bold]{data['name']}[/bold] ({data['status']})")
        if data.get("description"):
                _indent(data['description'])
        if data.get("motivation"):
            _indent(f"[italic]Motivation:[/italic] {data['motivation']}")
        if data.get("counts"):
            c = data["counts"]
            _indent(f"Goals: {c['goals']}  |  Tasks: {c['tasks_todo']} todo, {c['tasks_in_progress']} active, {c['tasks_done']} done")


@project_app.command("archive")
def project_archive(id: str = typer.Argument(...)):
    with _client() as c:
        resp = c.patch(f"/projects/{id}", json={"status": "archived"})
        _handle_error(resp)
    console.print("[yellow]Archived.[/yellow]")


# --- Goals ---

goals_app = typer.Typer(help="List goals")
app.add_typer(goals_app, name="goals")


@goals_app.callback(invoke_without_command=True)
def list_goals(
    ctx: typer.Context,
    project: str = typer.Option(None, "--project", help="Project ID"),
    json_out: bool = typer.Option(False, "--json"),
):
    if ctx.invoked_subcommand is not None:
        return
    if not project:
        console.print("[red]--project is required for listing goals[/red]")
        raise typer.Exit(1)
    with _client() as c:
        resp = c.get(f"/projects/{project}/goals")
        _handle_error(resp)
        data = resp.json()

    def show(d):
        table = Table(title="Goals")
        table.add_column("ID", style="dim", max_width=12)
        table.add_column("Title", style="bold")
        table.add_column("Status")
        table.add_column("Target")
        for g in d["data"]:
            table.add_row(g["id"][:12], g["title"], g["status"], g.get("target_date") or "-")
        console.print(table)

    _json_or_table(data, json_out, show)


goal_app = typer.Typer(help="Goal operations")
app.add_typer(goal_app, name="goal")


@goal_app.command("create")
def goal_create(
    project: str = typer.Argument(..., help="Project ID"),
    title: str = typer.Argument(...),
    desc: str = typer.Option("", "--desc"),
    motivation: str = typer.Option("", "--motivation", "-m", help="Why is this goal important?"),
    target: str = typer.Option(None, "--target", help="Target date (YYYY-MM-DD)"),
    json_out: bool = typer.Option(False, "--json"),
):
    with _client() as c:
        body = {"title": title, "description": desc, "motivation": motivation}
        if target:
            body["target_date"] = target
        resp = c.post(f"/projects/{project}/goals", json=body)
        _handle_error(resp)
        data = resp.json()["data"]

    if json_out:
        console.print_json(json.dumps(data))
    else:
        console.print(f"[green]Created goal:[/green] {data['title']} ({data['id'][:12]})")


@goal_app.command("show")
def goal_show(id: str = typer.Argument(...), json_out: bool = typer.Option(False, "--json")):
    with _client() as c:
        resp = c.get(f"/goals/{id}")
        _handle_error(resp)
        data = resp.json()["data"]

    if json_out:
        console.print_json(json.dumps(data))
    else:
        console.print(f"[bold]{data['title']}[/bold] ({data['status']})")
        if data.get("description"):
                _indent(data['description'])
        if data.get("motivation"):
            _indent(f"[italic]Motivation:[/italic] {data['motivation']}")
        if data.get("target_date"):
            _indent(f"Target: {data['target_date']}")


@goal_app.command("complete")
def goal_complete(id: str = typer.Argument(...)):
    with _client() as c:
        resp = c.patch(f"/goals/{id}", json={"status": "completed"})
        _handle_error(resp)
    console.print("[green]Goal completed![/green]")


# --- Tasks ---

@app.command("tasks")
def list_tasks(
    project: str = typer.Option(None, "--project"),
    status: str = typer.Option(None, "--status"),
    priority: str = typer.Option(None, "--priority"),
    blocked: bool = typer.Option(False, "--blocked", help="Show only blocked tasks"),
    json_out: bool = typer.Option(False, "--json"),
):
    params = {}
    if project:
        params["project_id"] = project
    if status:
        params["status"] = status
    else:
        params["status"] = "todo,in_progress"
    if priority:
        params["priority"] = priority
    if blocked:
        params["blocked"] = "true"

    with _client() as c:
        resp = c.get("/tasks", params=params)
        _handle_error(resp)
        data = resp.json()

    def show(d):
        table = Table(title="Tasks")
        table.add_column("ID", style="dim", max_width=12)
        table.add_column("Project", style="cyan")
        table.add_column("Title", style="bold")
        table.add_column("Status")
        table.add_column("Priority")
        for t in d["data"]:
            pstyle = {"critical": "red bold", "high": "red", "medium": "yellow", "low": "dim"}.get(t["priority"], "")
            table.add_row(t["id"][:12], t.get("project_name", ""), t["title"], t["status"], f"[{pstyle}]{t['priority']}[/{pstyle}]")
        console.print(table)

    _json_or_table(data, json_out, show)


task_app = typer.Typer(help="Task operations")
app.add_typer(task_app, name="task")


@task_app.command("create")
def task_create(
    project: str = typer.Argument(..., help="Project ID"),
    title: str = typer.Argument(...),
    desc: str = typer.Option("", "--desc"),
    rationale: str = typer.Option("", "--rationale", "-r", help="Why is this task needed?"),
    priority: str = typer.Option("medium", "--priority"),
    goal: str = typer.Option(None, "--goal", help="Goal ID"),
    blocked_by: str = typer.Option(None, "--blocked-by", help="Comma-separated blocker task IDs"),
    json_out: bool = typer.Option(False, "--json"),
):
    body = {"title": title, "description": desc, "rationale": rationale, "priority": priority}
    if goal:
        body["goal_id"] = goal
    if blocked_by:
        body["blocked_by"] = [x.strip() for x in blocked_by.split(",")]

    with _client() as c:
        resp = c.post(f"/projects/{project}/tasks", json=body)
        _handle_error(resp)
        data = resp.json()["data"]

    if json_out:
        console.print_json(json.dumps(data))
    else:
        console.print(f"[green]Created task:[/green] {data['title']} ({data['id'][:12]})")


@task_app.command("show")
def task_show(id: str = typer.Argument(...), json_out: bool = typer.Option(False, "--json")):
    with _client() as c:
        resp = c.get(f"/tasks/{id}")
        _handle_error(resp)
        data = resp.json()["data"]

    if json_out:
        console.print_json(json.dumps(data))
    else:
        blocked_marker = " [red](BLOCKED)[/red]" if data.get("is_blocked") else ""
        pname = data.get("project_name", "")
        console.print(f"[bold]{data['title']}[/bold] [{data['status']}] {data['priority']}{blocked_marker}")
        if pname:
            _indent(f"Project: [cyan]{pname}[/cyan]")
        if data.get("description"):
            _indent(data['description'])
        if data.get("rationale"):
            _indent(f"[italic]Rationale:[/italic] {data['rationale']}")
        if data.get("blocked_by"):
            _indent("[red]Blocked by:[/red]")
            for b in data["blocked_by"]:
                _indent(f"- {b['title']} ({b['status']})", left=4)
        if data.get("blocks"):
            _indent("[yellow]Blocks:[/yellow]")
            for b in data["blocks"]:
                _indent(f"- {b['title']} ({b['status']})", left=4)


@task_app.command("start")
def task_start(id: str = typer.Argument(...)):
    with _client() as c:
        resp = c.patch(f"/tasks/{id}", json={"status": "in_progress"})
        _handle_error(resp)
    console.print("[cyan]Task started.[/cyan]")


@task_app.command("done")
def task_done(id: str = typer.Argument(...)):
    with _client() as c:
        resp = c.patch(f"/tasks/{id}", json={"status": "done"})
        _handle_error(resp)
    console.print("[green]Task completed![/green]")


@task_app.command("block")
def task_block(
    id: str = typer.Argument(..., help="Task to be blocked"),
    by: str = typer.Option(..., "--by", help="Blocker task ID"),
):
    with _client() as c:
        resp = c.post(f"/tasks/{id}/dependencies", json={"blocker_id": by})
        _handle_error(resp)
    console.print("[yellow]Dependency added.[/yellow]")


# --- Work Log ---

@app.command("log")
def log_entry(
    description: str = typer.Argument(...),
    project: str = typer.Option(None, "--project", help="Project ID"),
    task: str = typer.Option(None, "--task", help="Task ID"),
    commit: list[str] = typer.Option(None, "--commit", help="Git commit hash (repeatable)"),
    repo: str = typer.Option(None, "--repo"),
    branch: str = typer.Option(None, "--branch"),
    json_out: bool = typer.Option(False, "--json"),
):
    body: dict = {"description": description}
    if project:
        body["project_id"] = project
    if task:
        body["task_id"] = task
    if commit or repo or branch:
        git_info: dict = {}
        if repo:
            git_info["repo"] = repo
        if branch:
            git_info["branch"] = branch
        if commit:
            git_info["commits"] = list(commit)
        body["metadata"] = {"git": git_info}

    with _client() as c:
        resp = c.post("/log", json=body)
        _handle_error(resp)
        data = resp.json()["data"]

    if json_out:
        console.print_json(json.dumps(data))
    else:
        console.print(f"[green]Logged:[/green] {data['description']}")


# --- Summary commands ---

@app.command("summary")
def summary(json_out: bool = typer.Option(False, "--json")):
    with _client() as c:
        resp = c.get("/summary")
        _handle_error(resp)
        data = resp.json()["data"]

    if json_out:
        console.print_json(json.dumps(data))
        return

    console.print("[bold]Summary[/bold]")
    console.print()
    for p in data.get("active_projects", []):
        ts = p["tasks_summary"]
        _indent(f"[bold]{p['name']}[/bold] — {p['goals_active']} goals, "
                f"{ts.get('todo', 0)} todo, {ts.get('in_progress', 0)} active, "
                f"{ts.get('done', 0)} done, {p['blocked_tasks']} blocked")
        if p.get("motivation"):
            _indent(f"[dim]{p['motivation']}[/dim]", left=4)

    if data.get("next_actions"):
        console.print()
        console.print("[bold]Next up:[/bold]")
        for n in data["next_actions"][:5]:
            _indent(f"[{n['priority']}] {n['title']} ({n['project_name']})")

    if data.get("blocked_tasks"):
        console.print()
        console.print("[bold red]Blocked:[/bold red]")
        for bt in data["blocked_tasks"]:
            blockers = ", ".join(b["title"] for b in bt["blocked_by"])
            _indent(f"{bt['title']} — waiting on: {blockers}")


@app.command("today")
def today(json_out: bool = typer.Option(False, "--json")):
    with _client() as c:
        resp = c.get("/summary/today")
        _handle_error(resp)
        data = resp.json()["data"]

    if json_out:
        console.print_json(json.dumps(data))
        return

    console.print("[bold]Today[/bold]")
    if data.get("log_entries"):
        console.print()
        for e in data["log_entries"]:
            time = e["created_at"][11:16] if len(e["created_at"]) > 16 else ""
            _indent(f"[dim]{time}[/dim] {e['description']}")
    else:
        _indent("No activity logged today.")

    if data.get("tasks_completed"):
        console.print()
        console.print("[green]Completed:[/green]")
        by_proj: dict[str, list] = {}
        for t in data["tasks_completed"]:
            pname = t.get("project_name", "Unknown")
            by_proj.setdefault(pname, []).append(t)
        for pname, tasks in by_proj.items():
            _indent(f"[bold]{pname}[/bold]")
            for t in tasks:
                _indent(f"✓ {t['title']}", left=4)


@app.command("next")
def next_actions(json_out: bool = typer.Option(False, "--json")):
    with _client() as c:
        resp = c.get("/summary/next")
        _handle_error(resp)
        data = resp.json()["data"]

    if json_out:
        console.print_json(json.dumps(data))
        return

    console.print("[bold]Next actions[/bold]")
    if data.get("tasks"):
        for t in data["tasks"]:
            pstyle = {"critical": "red bold", "high": "red", "medium": "yellow", "low": "dim"}.get(t["priority"], "")
            _indent(f"[{pstyle}]{t['priority']}[/{pstyle}] {t['title']} ({t['project_name']})")
            if t.get("rationale"):
                _indent(f"[dim]{t['rationale']}[/dim]", left=4)
    else:
        _indent("Nothing queued up.")


@app.command("weekly")
def weekly_report(
    weeks_back: int = typer.Option(0, "--weeks-back", "-w", help="0=this week, 1=last week, etc."),
    project: str = typer.Option(None, "--project", "-p", help="Filter by project ID"),
    json_out: bool = typer.Option(False, "--json"),
):
    params: dict = {"weeks_back": weeks_back}
    if project:
        params["project_id"] = project
    with _client() as c:
        resp = c.get("/summary/weekly", params=params)
        _handle_error(resp)
        data = resp.json()["data"]

    if json_out:
        console.print_json(json.dumps(data))
        return

    console.print(f"[bold]Weekly Report[/bold] ({data['week_start'][:10]} → {data['week_end'][:10]})")
    _indent(f"{data['total_log_entries']} entries | "
            f"{data['total_tasks_completed']} tasks completed | "
            f"{data['total_tasks_created']} tasks created | "
            f"{data['total_goals_completed']} goals completed")

    if data.get("by_project"):
        console.print()
        console.print("[bold]By project:[/bold]")
        for i, p in enumerate(data["by_project"]):
            if i > 0:
                console.print()
            _indent(f"[bold]{p['project_name']}[/bold] — {p['entry_count']} entries")
            if p.get("project_motivation"):
                _indent(f"[dim]{p['project_motivation']}[/dim]", left=4)
            for e in p["entries"]:
                time = e["created_at"][11:16] if len(e["created_at"]) > 16 else ""
                day = e["created_at"][:10]
                _indent(f"[dim]{day} {time}[/dim] {e['description']}", left=4)

    if data.get("tasks_completed"):
        console.print()
        console.print("[green]Tasks completed:[/green]")
        by_proj: dict[str, list] = {}
        for t in data["tasks_completed"]:
            pname = t.get("project_name", "Unknown")
            by_proj.setdefault(pname, []).append(t)
        for pname, tasks in by_proj.items():
            _indent(f"[bold]{pname}[/bold]")
            for t in tasks:
                _indent(f"✓ {t['title']}", left=4)

    if not data.get("by_project") and not data.get("tasks_completed"):
        _indent("No activity this week.")


@app.command("export")
def export_weekly(
    weeks_back: int = typer.Option(0, "--weeks-back", "-w", help="0=this week, 1=last week, etc."),
    project: str = typer.Option(None, "--project", "-p", help="Filter by project ID"),
    output: str = typer.Option(None, "--output", "-o", help="Save to file (default: print to stdout)"),
):
    params: dict = {"weeks_back": weeks_back}
    if project:
        params["project_id"] = project
    with _client() as c:
        resp = c.get("/summary/export/weekly", params=params)
        _handle_error(resp)
        markdown = resp.text

    if output:
        with open(output, "w") as f:
            f.write(markdown)
        console.print(f"[green]Exported to {output}[/green]")
    else:
        console.print(markdown)


@app.command("blocked")
def blocked_tasks(json_out: bool = typer.Option(False, "--json")):
    with _client() as c:
        resp = c.get("/summary/blocked")
        _handle_error(resp)
        data = resp.json()["data"]

    if json_out:
        console.print_json(json.dumps(data))
        return

    if not data:
        console.print("No blocked tasks.")
        return

    console.print("[bold red]Blocked tasks[/bold red]")
    for bt in data:
        blockers = ", ".join(b["title"] for b in bt["blocked_by"])
        _indent(f"{bt['title']} — waiting on: {blockers}")


def _kill_stale_server(port: int):
    """Kill any process listening on the given port.

    On macOS, launchctl bootout can leave orphaned server processes that
    hold the port open.  This ensures a clean slate before starting.
    """
    import signal
    import subprocess

    result = subprocess.run(
        ["lsof", "-ti", f":{port}"],
        capture_output=True, text=True,
    )
    pids = result.stdout.strip().split()
    my_pid = str(os.getpid())
    for pid in pids:
        if pid and pid != my_pid:
            try:
                os.kill(int(pid), signal.SIGTERM)
                console.print(f"[yellow]Killed stale process {pid} on port {port}[/yellow]")
            except (ProcessLookupError, PermissionError):
                pass


def _stop_service():
    """Stop the logbook service and kill any stale processes on the port."""
    import platform
    import subprocess

    from logbook.config import settings

    system = platform.system()

    if system == "Linux":
        console.print("[cyan]Stopping logbook service (systemd)...[/cyan]")
        subprocess.run(["systemctl", "--user", "stop", "logbook"],
                       capture_output=True, text=True)
    elif system == "Darwin":
        label = "com.logbook.server"
        plist_path = os.path.expanduser(f"~/Library/LaunchAgents/{label}.plist")
        console.print("[cyan]Stopping logbook service (launchd)...[/cyan]")
        # Try unload first (more reliable), fall back to bootout
        if os.path.exists(plist_path):
            subprocess.run(["launchctl", "unload", plist_path],
                           capture_output=True, text=True)
        else:
            subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}", label],
                           capture_output=True, text=True)
        _kill_stale_server(settings.port)
    # Errors ignored — service might not be running


def _start_service():
    """Start the logbook service, killing any stale processes first."""
    import platform
    import subprocess
    import time

    from logbook.config import settings

    system = platform.system()

    if system == "Linux":
        console.print("[cyan]Starting logbook service (systemd)...[/cyan]")
        result = subprocess.run(["systemctl", "--user", "start", "logbook"],
                                capture_output=True, text=True)
        if result.returncode != 0:
            console.print(f"[red]Start failed:[/red] {result.stderr.strip()}")
            raise typer.Exit(1)
    elif system == "Darwin":
        label = "com.logbook.server"
        plist_path = os.path.expanduser(f"~/Library/LaunchAgents/{label}.plist")
        if not os.path.exists(plist_path):
            console.print(f"[red]No launchd plist found at {plist_path}[/red]")
            console.print("Run [bold]logbook install-service[/bold] first.")
            raise typer.Exit(1)
        _kill_stale_server(settings.port)
        console.print("[cyan]Starting logbook service (launchd)...[/cyan]")
        result = subprocess.run(["launchctl", "load", plist_path],
                                capture_output=True, text=True)
        if result.returncode != 0:
            console.print(f"[red]Start failed:[/red] {result.stderr.strip()}")
            raise typer.Exit(1)
    else:
        console.print(f"[red]Unsupported platform: {system}[/red]")
        console.print("Start the server manually: uvicorn logbook.main:app --host 127.0.0.1 --port 8000")
        raise typer.Exit(1)

    console.print("[green]Logbook service started.[/green]")


def _restart_service():
    """Restart the logbook service using the platform's service manager."""
    _stop_service()
    _start_service()


@app.command("restart")
def restart():
    """Reinstall the logbook package and restart the service."""
    import subprocess

    from logbook.config import settings

    console.print("[cyan]Reinstalling logbook...[/cyan]")
    result = subprocess.run(
        ["pip", "install", "."],
        capture_output=True, text=True,
        cwd=settings.project_dir,
    )
    if result.returncode != 0:
        console.print(f"[red]Install failed:[/red] {result.stderr.strip()}")
        raise typer.Exit(1)
    console.print("[green]Installed.[/green]")

    _restart_service()


@app.command("install-service")
def install_service():
    """Install the logbook server as a system service (systemd on Linux, launchd on macOS)."""
    import platform
    import subprocess

    from logbook.config import settings

    system = platform.system()

    if system == "Linux":
        unit_dir = os.path.expanduser("~/.config/systemd/user")
        unit_path = os.path.join(unit_dir, "logbook.service")
        os.makedirs(unit_dir, exist_ok=True)

        # Try to find uvicorn in PATH, fallback to python -m uvicorn
        uvicorn_result = subprocess.run(
            ["which", "uvicorn"], capture_output=True, text=True
        )
        uvicorn_path = uvicorn_result.stdout.strip()

        if not uvicorn_path:
            # Fallback: use python -m uvicorn
            exec_start = f"{sys.executable} -m uvicorn logbook.main:app --host {settings.host} --port {settings.port}"
        else:
            exec_start = f"{uvicorn_path} logbook.main:app --host {settings.host} --port {settings.port}"

        unit = f"""[Unit]
Description=Logbook API Server
After=network.target

[Service]
Type=simple
Environment=LOGBOOK_DB_PATH={settings.db_path}
ExecStart={exec_start}
Restart=on-failure

[Install]
WantedBy=default.target
"""
        with open(unit_path, "w") as f:
            f.write(unit)
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        # Stop existing service if running (systemd kills the tracked PID)
        subprocess.run(["systemctl", "--user", "stop", "logbook"],
                       capture_output=True, text=True)
        subprocess.run(["systemctl", "--user", "enable", "logbook"], check=True)
        subprocess.run(["systemctl", "--user", "start", "logbook"], check=True)
        console.print(f"[green]Installed and started systemd service.[/green]")
        console.print(f"  Unit file: {unit_path}")

    elif system == "Darwin":
        label = "com.logbook.server"
        plist_dir = os.path.expanduser("~/Library/LaunchAgents")
        plist_path = os.path.join(plist_dir, f"{label}.plist")
        os.makedirs(plist_dir, exist_ok=True)

        # Try to find uvicorn in PATH, fallback to pipx venv
        uvicorn_result = subprocess.run(
            ["which", "uvicorn"], capture_output=True, text=True
        )
        uvicorn_path = uvicorn_result.stdout.strip()

        if not uvicorn_path:
            # Fallback: use Python from current interpreter and run uvicorn as module
            uvicorn_path = sys.executable

        log_dir = os.path.expanduser("~/Library/Logs/logbook")
        os.makedirs(log_dir, exist_ok=True)

        # Build ProgramArguments: if using python executable, use -m uvicorn; otherwise use uvicorn directly
        if uvicorn_path == sys.executable:
            program_args = f"""        <string>{uvicorn_path}</string>
        <string>-m</string>
        <string>uvicorn</string>
        <string>logbook.main:app</string>"""
        else:
            program_args = f"""        <string>{uvicorn_path}</string>
        <string>logbook.main:app</string>"""

        plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{label}</string>
    <key>ProgramArguments</key>
    <array>
{program_args}
        <string>--host</string>
        <string>{settings.host}</string>
        <string>--port</string>
        <string>{str(settings.port)}</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>LOGBOOK_DB_PATH</key>
        <string>{settings.db_path}</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{log_dir}/stdout.log</string>
    <key>StandardErrorPath</key>
    <string>{log_dir}/stderr.log</string>
</dict>
</plist>
"""
        with open(plist_path, "w") as f:
            f.write(plist)
        # Stop existing service and kill any orphaned processes on the port
        subprocess.run(["launchctl", "unload", plist_path],
                       capture_output=True, text=True)
        _kill_stale_server(settings.port)
        subprocess.run(["launchctl", "load", plist_path],
                       capture_output=True, text=True)
        console.print(f"[green]Installed and started launchd service.[/green]")
        console.print(f"  Plist: {plist_path}")
        console.print(f"  Logs: {log_dir}/")

    else:
        console.print(f"[red]Unsupported platform: {system}[/red]")
        raise typer.Exit(1)


@app.command("import-db")
def import_db(
    source: str = typer.Argument(..., help="Path to the database file to import"),
):
    """Import a logbook database file, replacing the current one.

    Stops the service, checkpoints the source WAL, copies it to the
    configured LOGBOOK_DB_PATH location, and restarts the service.
    """
    import shutil
    import sqlite3 as stdlib_sqlite
    import subprocess

    from logbook.config import settings

    source_path = os.path.expanduser(source)
    if not os.path.exists(source_path):
        console.print(f"[red]File not found:[/red] {source_path}")
        raise typer.Exit(1)

    dest_path = settings.db_path
    console.print(f"Source:      {source_path}")
    console.print(f"Destination: {dest_path}")

    if os.path.abspath(source_path) == os.path.abspath(dest_path):
        console.print("[yellow]Source and destination are the same file.[/yellow]")
        raise typer.Exit(1)

    # Checkpoint the source WAL so we get a clean single file
    try:
        conn = stdlib_sqlite.connect(source_path)
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        conn.close()
        console.print("[green]Source WAL checkpointed.[/green]")
    except Exception as e:
        console.print(f"[yellow]WAL checkpoint skipped:[/yellow] {e}")

    # Stop the service before replacing the file
    _stop_service()

    # Ensure destination directory exists
    os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)

    # Remove old WAL/SHM files at destination
    for suffix in ("-wal", "-shm"):
        old = dest_path + suffix
        if os.path.exists(old):
            os.remove(old)

    # Copy
    shutil.copy2(source_path, dest_path)
    console.print(f"[green]Database imported to {dest_path}[/green]")

    # Start the service back up
    _start_service()


@app.command("backup")
def backup(
    output: str = typer.Argument(..., help="Path to save the backup"),
):
    """Create a clean backup of the current database.

    Checkpoints the WAL first so the backup is a single self-contained file.
    """
    import shutil
    import sqlite3 as stdlib_sqlite

    from logbook.config import settings

    source_path = settings.db_path
    output_path = os.path.expanduser(output)

    if not os.path.exists(source_path):
        console.print(f"[red]Database not found:[/red] {source_path}")
        raise typer.Exit(1)

    # Checkpoint WAL
    try:
        conn = stdlib_sqlite.connect(source_path)
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        conn.close()
    except Exception as e:
        console.print(f"[yellow]WAL checkpoint skipped:[/yellow] {e}")

    shutil.copy2(source_path, output_path)
    console.print(f"[green]Backup saved to {output_path}[/green]")


@app.command("search")
def search_cmd(
    query: str = typer.Argument(..., help="Search keywords"),
    type: str = typer.Option(None, "--type", "-t", help="Filter by type: project,goal,task,work_log_entry"),
    limit: int = typer.Option(20, "--limit"),
    json_out: bool = typer.Option(False, "--json"),
):
    params: dict = {"q": query, "limit": limit}
    if type:
        params["type"] = type

    with _client() as c:
        resp = c.get("/search", params=params)
        _handle_error(resp)
        data = resp.json()["data"]

    if json_out:
        console.print_json(json.dumps(data))
        return

    if not data["results"]:
        console.print("No results found.")
        return

    console.print(f"[bold]Search results for \"{query}\"[/bold] ({data['total']} matches)")
    console.print()
    type_styles = {"project": "blue", "goal": "magenta", "task": "cyan", "work_log_entry": "green"}
    for r in data["results"]:
        style = type_styles.get(r["entity_type"], "white")
        label = r["entity_type"].replace("_", " ")
        title = r["title_snippet"].replace(">>>", "[bold]").replace("<<<", "[/bold]")
        body = r["body_snippet"].replace(">>>", "[bold]").replace("<<<", "[/bold]")
        _indent(f"[{style}]{label}[/{style}] {title}")
        if body.strip():
            _indent(f"[dim]{body}[/dim]", left=4)
        _indent(f"[dim]id: {r['entity_id']}[/dim]", left=4)
        console.print()


if __name__ == "__main__":
    app()
