const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);
const content = $("#content");

let currentTab = "summary";
let weeksBack = 0;
let includeArchived = false;

// --- API ---

async function api(path) {
  const resp = await fetch(path);
  if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
  const json = await resp.json();
  return json.data;
}

// --- Helpers ---

function esc(str) {
  const el = document.createElement("span");
  el.textContent = str;
  return el.innerHTML;
}

function time(isoStr) {
  if (!isoStr || isoStr.length < 16) return "";
  try {
    const d = new Date(isoStr);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return isoStr.slice(11, 16);
  }
}

function date(isoStr) {
  if (!isoStr) return "";
  return isoStr.slice(0, 10);
}

function shortDate(isoStr) {
  if (!isoStr) return "";
  try {
    const d = new Date(isoStr);
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  } catch {
    return isoStr.slice(5, 10);
  }
}

function prettyDate(isoStr) {
  if (!isoStr) return "";
  try {
    const d = new Date(isoStr.slice(0, 10) + "T12:00:00");
    return d.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" });
  } catch {
    return isoStr.slice(0, 10);
  }
}

function commitInfo(metadata) {
  if (!metadata) return "";
  const git = metadata.git || {};
  let commits = git.commits || [];
  // Legacy flat format
  if (!commits.length && metadata.commit) commits = [metadata.commit];
  if (!commits.length) return "";
  const short = commits.map((c) => c.slice(0, 7)).join(", ");
  const repo = git.repo || metadata.repo || "";
  const branch = git.branch || metadata.branch || "";
  let label = short;
  if (repo && branch) label = `${short} in ${repo}/${branch}`;
  else if (repo) label = `${short} in ${repo}`;
  else if (branch) label = `${short} on ${branch}`;
  return `<span class="commit-info">${esc(label)}</span>`;
}

function priorityClass(p) {
  return `priority-${p}`;
}

function groupBy(arr, keyFn) {
  const groups = {};
  for (const item of arr) {
    const key = keyFn(item);
    (groups[key] ||= []).push(item);
  }
  return groups;
}

// --- Task toggle ---

function toggleTaskDetails(row) {
  const toggle = row.querySelector(".task-toggle");
  if (!toggle) return;
  const details = row.tagName === "DIV" && row.classList.contains("task-row")
    ? row.nextElementSibling
    : row.querySelector(".task-details");
  if (!details || !details.classList.contains("task-details")) return;
  const collapsed = details.classList.toggle("collapsed");
  toggle.classList.toggle("expanded", !collapsed);
}

function wireTaskToggles(container) {
  for (const row of container.querySelectorAll(".task-expandable, .item-expandable")) {
    row.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleTaskDetails(row);
    });
  }
}

// --- Renderers ---

async function toggleProjectDetail(card, projectId) {
  const existing = card.querySelector(".card-detail");
  if (existing) {
    existing.remove();
    card.classList.remove("expanded");
    return;
  }

  // Collapse any other expanded card first
  for (const other of $$(".card-clickable.expanded")) {
    other.querySelector(".card-detail")?.remove();
    other.classList.remove("expanded");
  }

  card.classList.add("expanded");
  const detail = document.createElement("div");
  detail.className = "card-detail";
  detail.innerHTML = `<p class="loading">Loading...</p>`;
  card.appendChild(detail);

  try {
    const [tasksData, logData] = await Promise.all([
      api(`/tasks?project_id=${projectId}&status=todo,in_progress,done&limit=20`),
      api(`/log?project_id=${projectId}&limit=10`),
    ]);

    // tasksData is an array (from ListResponse), logData is also an array
    const tasks = Array.isArray(tasksData) ? tasksData : [];
    const logs = Array.isArray(logData) ? logData : [];

    let html = "";

    // Tasks by status
    const activeTasks = tasks.filter((t) => t.status !== "done");
    const doneTasks = tasks.filter((t) => t.status === "done");

    if (activeTasks.length) {
      html += `<div class="detail-section"><div class="detail-label">Tasks</div>`;
      for (const t of activeTasks) {
        const statusClass = t.status === "in_progress" ? "pill pill-active" : "pill pill-todo";
        const hasDetails = t.description || t.rationale || t.notes;
        html += `
          <div class="task-row${hasDetails ? " task-expandable" : ""}">
            <span class="pill pill-priority-${t.priority}">${esc(t.priority)}</span>
            <span class="task-title">${esc(t.title)}</span>
            <span class="${statusClass}">${esc(t.status.replace("_", " "))}</span>
            ${hasDetails ? '<span class="task-toggle">&#9654;</span>' : ""}
          </div>`;
        if (hasDetails) {
          html += `<div class="task-details collapsed">`;
          if (t.description) {
            html += `<div class="task-detail-field"><span class="task-detail-label">Description</span> ${esc(t.description)}</div>`;
          }
          if (t.rationale) {
            html += `<div class="task-detail-field"><span class="task-detail-label">Rationale</span> ${esc(t.rationale)}</div>`;
          }
          if (t.notes) {
            html += `<div class="task-detail-field"><span class="task-detail-label">Notes</span> ${esc(t.notes)}</div>`;
          }
          html += `</div>`;
        }
      }
      html += `</div>`;
    }

    if (doneTasks.length) {
      html += `<div class="detail-section"><div class="detail-label">Completed</div>`;
      for (const t of doneTasks) {
        const hasDetails = t.description || t.rationale || t.notes;
        const completedDate = t.completed_at ? `<span class="task-completed-date">${esc(shortDate(t.completed_at))}</span>` : "";
        html += `
          <div class="task-row task-done${hasDetails ? " task-expandable" : ""}">
            <span class="check">&#10003;</span> ${esc(t.title)} ${completedDate}
            ${hasDetails ? '<span class="task-toggle">&#9654;</span>' : ""}
          </div>`;
        if (hasDetails) {
          html += `<div class="task-details collapsed">`;
          if (t.description) {
            html += `<div class="task-detail-field"><span class="task-detail-label">Description</span> ${esc(t.description)}</div>`;
          }
          if (t.rationale) {
            html += `<div class="task-detail-field"><span class="task-detail-label">Rationale</span> ${esc(t.rationale)}</div>`;
          }
          if (t.notes) {
            html += `<div class="task-detail-field"><span class="task-detail-label">Notes</span> ${esc(t.notes)}</div>`;
          }
          html += `</div>`;
        }
      }
      html += `</div>`;
    }

    if (logs.length) {
      html += `<div class="detail-section"><div class="detail-label">Recent work</div>`;
      for (const e of logs) {
        const ci = commitInfo(e.metadata);
        html += `
          <div class="timeline-entry">
            <div class="timeline-time"><span class="timeline-date">${esc(shortDate(e.created_at))}</span> ${esc(time(e.created_at))}</div>
            <div class="timeline-desc">${esc(e.description)}${ci ? " " + ci : ""}</div>
          </div>`;
      }
      html += `</div>`;
    }

    if (!tasks.length && !logs.length) {
      html = `<p class="empty">No tasks or log entries.</p>`;
    }

    detail.innerHTML = html;
    wireTaskToggles(detail);
  } catch (err) {
    detail.innerHTML = `<p class="error">Failed to load: ${esc(err.message)}</p>`;
  }
}

function renderSummary(data, archivedProjects) {
  let html = "";

  // Include Archived toggle
  html += `<div class="summary-controls">
    <label class="toggle-label">
      <input type="checkbox" id="archived-toggle" ${includeArchived ? "checked" : ""} />
      Include Archived
    </label>
  </div>`;

  // Project cards
  const projects = data.active_projects || [];
  const archived = archivedProjects || [];
  const allProjects = includeArchived ? [...projects, ...archived] : projects;

  if (allProjects.length) {
    html += `<div class="card-grid">`;
    for (const p of allProjects) {
      const ts = p.tasks_summary || {};
      const isArchived = p.status === "archived";
      const archiveLabel = isArchived ? "Unarchive" : "Archive";
      const archiveAction = isArchived ? "active" : "archived";
      html += `
        <div class="card card-clickable${isArchived ? " card-archived" : ""}" data-project-id="${esc(p.id)}">
          <button class="card-archive-btn" data-project-id="${esc(p.id)}" data-action="${archiveAction}" title="${archiveLabel}">${archiveLabel}</button>
          <h3>${esc(p.name)}${isArchived ? ' <span class="pill pill-archived">archived</span>' : ""}</h3>
          ${p.motivation ? `<div class="motivation">${esc(p.motivation)}</div>` : ""}
          <div class="pills">
            ${ts.todo ? `<span class="pill pill-todo">${ts.todo} todo</span>` : ""}
            ${ts.in_progress ? `<span class="pill pill-active">${ts.in_progress} active</span>` : ""}
            ${ts.done ? `<span class="pill pill-done">${ts.done} done</span>` : ""}
            ${p.blocked_tasks ? `<span class="pill pill-blocked">${p.blocked_tasks} blocked</span>` : ""}
          </div>
        </div>`;
    }
    html += `</div>`;
  }

  // Next actions
  if (data.next_actions?.length) {
    html += `<div class="section"><div class="section-title">Next up</div>`;
    for (const n of data.next_actions) {
      const hasDetails = n.description || n.rationale;
      html += `
        <div class="item${hasDetails ? " item-expandable" : ""}">
          <div class="item-title">
            <span class="${priorityClass(n.priority)}">${esc(n.priority)}</span>
            ${esc(n.title)}
            <span class="item-meta">${esc(n.project_name)}</span>
            ${hasDetails ? '<span class="task-toggle">&#9654;</span>' : ""}
          </div>
          ${hasDetails ? `<div class="task-details collapsed">
            ${n.description ? `<div class="task-detail-field"><span class="task-detail-label">Description</span> ${esc(n.description)}</div>` : ""}
            ${n.rationale ? `<div class="task-detail-field"><span class="task-detail-label">Rationale</span> ${esc(n.rationale)}</div>` : ""}
          </div>` : ""}
        </div>`;
    }
    html += `</div>`;
  }

  // Blocked
  if (data.blocked_tasks?.length) {
    html += `<div class="section"><div class="section-title">Blocked</div>`;
    for (const bt of data.blocked_tasks) {
      const blockers = bt.blocked_by.map((b) => esc(b.title)).join(", ");
      const hasDetails = bt.description || bt.rationale;
      html += `
        <div class="item${hasDetails ? " item-expandable" : ""}">
          <div class="item-title">
            ${esc(bt.title)}
            ${hasDetails ? '<span class="task-toggle">&#9654;</span>' : ""}
          </div>
          <div class="item-meta">waiting on: ${blockers}</div>
          ${hasDetails ? `<div class="task-details collapsed">
            ${bt.description ? `<div class="task-detail-field"><span class="task-detail-label">Description</span> ${esc(bt.description)}</div>` : ""}
            ${bt.rationale ? `<div class="task-detail-field"><span class="task-detail-label">Rationale</span> ${esc(bt.rationale)}</div>` : ""}
          </div>` : ""}
        </div>`;
    }
    html += `</div>`;
  }

  if (!data.active_projects?.length) {
    html = `<p class="empty">No active projects.</p>`;
  }

  content.innerHTML = html;

  // Wire up card clicks
  for (const card of $$(".card-clickable")) {
    card.addEventListener("click", (e) => {
      // Don't toggle if clicking inside the detail area or archive button
      if (e.target.closest(".card-detail") || e.target.closest(".card-archive-btn")) return;
      toggleProjectDetail(card, card.dataset.projectId);
    });
  }

  // Wire up archive buttons
  for (const btn of $$(".card-archive-btn")) {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const pid = btn.dataset.projectId;
      const newStatus = btn.dataset.action;
      try {
        await fetch(`/projects/${pid}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: newStatus }),
        });
        loadTab("summary");
      } catch (err) {
        alert(`Failed to update project: ${err.message}`);
      }
    });
  }

  // Wire up task detail toggles
  wireTaskToggles(content);

  // Wire up archived toggle
  const toggle = $("#archived-toggle");
  if (toggle) {
    toggle.addEventListener("change", () => {
      includeArchived = toggle.checked;
      loadTab("summary");
    });
  }
}

function renderToday(data) {
  let html = "";

  // Log entries grouped by project
  if (data.log_entries?.length) {
    html += `<div class="section"><div class="section-title">Work logged today</div>`;
    for (const e of data.log_entries) {
      const ci = commitInfo(e.metadata);
      const proj = e.project_name ? `<span class="item-meta" style="font-weight:600;color:var(--accent)">${esc(e.project_name)}</span>` : "";
      html += `
        <div class="timeline-entry">
          <div class="timeline-time">${esc(time(e.created_at))}</div>
          <div class="timeline-desc">${esc(e.description)}${ci ? " " + ci : ""} ${proj}</div>
        </div>`;
    }
    html += `</div>`;
  }

  // Completed tasks grouped by project
  if (data.tasks_completed?.length) {
    const byProj = groupBy(data.tasks_completed, (t) => t.project_name || "Unknown");
    html += `<div class="section"><div class="section-title">Completed</div>`;
    for (const [pname, tasks] of Object.entries(byProj)) {
      html += `<div class="project-group">`;
      html += `<div class="project-group-header">${esc(pname)}</div>`;
      for (const t of tasks) {
        html += `<div class="item"><span class="check">&#10003;</span> ${esc(t.title)}</div>`;
      }
      html += `</div>`;
    }
    html += `</div>`;
  }

  if (!data.log_entries?.length && !data.tasks_completed?.length) {
    html = `<p class="empty">No activity logged today.</p>`;
  }

  content.innerHTML = html;
}

function renderWeekly(data) {
  let html = "";

  // Week navigation
  html += `
    <div class="week-nav">
      <button id="week-prev">&larr; Prev</button>
      <span>${date(data.week_start)} &rarr; ${date(data.week_end)}</span>
      <button id="week-next" ${weeksBack === 0 ? "disabled" : ""}>&rarr; Next</button>
    </div>`;

  // Stats bar
  html += `
    <div class="stats-bar">
      <div class="stat">
        <div class="stat-value">${data.total_log_entries}</div>
        <div class="stat-label">Entries</div>
      </div>
      <div class="stat">
        <div class="stat-value">${data.total_tasks_completed}</div>
        <div class="stat-label">Completed</div>
      </div>
      <div class="stat">
        <div class="stat-value">${data.total_tasks_created}</div>
        <div class="stat-label">Created</div>
      </div>
      <div class="stat">
        <div class="stat-value">${data.total_goals_completed}</div>
        <div class="stat-label">Goals</div>
      </div>
    </div>`;

  // By project
  if (data.by_project?.length) {
    html += `<div class="section"><div class="section-title">By project</div>`;
    for (const p of data.by_project) {
      html += `<div class="project-group">`;
      html += `<div class="project-group-header">${esc(p.project_name)} <span class="item-meta">&mdash; ${p.entry_count} entries</span></div>`;
      if (p.project_motivation) {
        html += `<div class="project-group-motivation">${esc(p.project_motivation)}</div>`;
      }
      const byDay = groupBy(p.entries, (e) => date(e.created_at));
      for (const [day, entries] of Object.entries(byDay)) {
        html += `<div class="day-header">${esc(prettyDate(day))}</div>`;
        for (const e of entries) {
          const ci = commitInfo(e.metadata);
          html += `
            <div class="timeline-entry">
              <div class="timeline-time">${esc(time(e.created_at))}</div>
              <div class="timeline-desc">${esc(e.description)}${ci ? " " + ci : ""}</div>
            </div>`;
        }
      }
      html += `</div>`;
    }
    html += `</div>`;
  }

  // Tasks completed
  if (data.tasks_completed?.length) {
    const byProj = groupBy(data.tasks_completed, (t) => t.project_name || "Unknown");
    html += `<div class="section"><div class="section-title">Tasks completed</div>`;
    for (const [pname, tasks] of Object.entries(byProj)) {
      html += `<div class="project-group">`;
      html += `<div class="project-group-header">${esc(pname)}</div>`;
      for (const t of tasks) {
        html += `<div class="item"><span class="check">&#10003;</span> ${esc(t.title)}</div>`;
      }
      html += `</div>`;
    }
    html += `</div>`;
  }

  if (!data.by_project?.length && !data.tasks_completed?.length) {
    html += `<p class="empty">No activity this week.</p>`;
  }

  content.innerHTML = html;

  // Wire up week navigation
  $("#week-prev")?.addEventListener("click", () => {
    weeksBack++;
    loadTab("weekly");
  });
  $("#week-next")?.addEventListener("click", () => {
    if (weeksBack > 0) {
      weeksBack--;
      loadTab("weekly");
    }
  });
}

// --- Help ---

function renderHelp() {
  content.innerHTML = `
<div class="help">
  <h2>Getting started</h2>
  <p>Logbook is a local work journal and planning tool. It runs on your machine, stores everything in a SQLite file, and is designed to work with Claude Code.</p>

  <h2>Dashboard tabs</h2>
  <dl>
    <dt>Summary</dt>
    <dd>Project cards with task counts. Click a card to expand and see its tasks, rationale, and recent work log.</dd>
    <dt>Today</dt>
    <dd>Timeline of today's logged work and completed tasks, grouped by project.</dd>
    <dt>Weekly</dt>
    <dd>Stats bar, entries grouped by project and day, completed tasks. Use the prev/next arrows to navigate weeks.</dd>
  </dl>

  <h2>Search</h2>
  <p>Type in the search box to search across projects, goals, tasks, and work log entries. Supports prefix matching and phrase search (<code>"exact phrase"</code>).</p>

  <h2>CLI commands</h2>

  <h3>Logging &amp; viewing</h3>
  <table>
    <tr><td><code>logbook log "description"</code></td><td>Log work (supports --project, --task, --commit, --repo, --branch)</td></tr>
    <tr><td><code>logbook log-update &lt;ID&gt;</code></td><td>Update a log entry (supports --description, --project, --task)</td></tr>
    <tr><td><code>logbook log-delete &lt;ID&gt;</code></td><td>Delete a log entry</td></tr>
    <tr><td><code>logbook tasks</code></td><td>List active tasks (supports --project, --status, --priority, --blocked)</td></tr>
    <tr><td><code>logbook summary</code></td><td>Full overview of all projects</td></tr>
    <tr><td><code>logbook today</code></td><td>Today's activity</td></tr>
    <tr><td><code>logbook next</code></td><td>What to work on next (ranked by priority, impact, age)</td></tr>
    <tr><td><code>logbook blocked</code></td><td>Show blocked tasks and what's blocking them</td></tr>
    <tr><td><code>logbook weekly</code></td><td>Weekly report (supports -w for weeks back, -p for project)</td></tr>
    <tr><td><code>logbook search "keyword"</code></td><td>Search everything (supports --type to filter)</td></tr>
    <tr><td><code>logbook export -o report.md</code></td><td>Export weekly report as markdown</td></tr>
  </table>

  <h3>Projects, goals &amp; tasks</h3>
  <table>
    <tr><td><code>logbook project create "name" --motivation "why"</code></td><td>Create a project</td></tr>
    <tr><td><code>logbook project show &lt;ID&gt;</code></td><td>Show project details</td></tr>
    <tr><td><code>logbook project archive &lt;ID&gt;</code></td><td>Archive a project</td></tr>
    <tr><td><code>logbook project unarchive &lt;ID&gt;</code></td><td>Restore an archived project to active</td></tr>
    <tr><td><code>logbook goal create &lt;PROJECT&gt; "title"</code></td><td>Create a goal (supports --target, --motivation)</td></tr>
    <tr><td><code>logbook goal show &lt;ID&gt;</code></td><td>Show goal details</td></tr>
    <tr><td><code>logbook goal complete &lt;ID&gt;</code></td><td>Mark a goal complete</td></tr>
    <tr><td><code>logbook task create &lt;PROJECT&gt; "title"</code></td><td>Create a task (supports --priority, --rationale, --goal, --blocked-by)</td></tr>
    <tr><td><code>logbook task show &lt;ID&gt;</code></td><td>Show task details with dependencies</td></tr>
    <tr><td><code>logbook task start &lt;ID&gt;</code></td><td>Mark a task in progress</td></tr>
    <tr><td><code>logbook task done &lt;ID&gt;</code></td><td>Complete a task</td></tr>
    <tr><td><code>logbook task block &lt;ID&gt; --by &lt;BLOCKER_ID&gt;</code></td><td>Add a task dependency</td></tr>
  </table>

  <h3>Backup &amp; restore</h3>
  <table>
    <tr><td><code>logbook backup</code></td><td>Backup database to configured backup_path</td></tr>
    <tr><td><code>logbook backup /path/to/file.db</code></td><td>Backup to a specific path</td></tr>
    <tr><td><code>logbook restore</code></td><td>Restore database from configured backup_path</td></tr>
    <tr><td><code>logbook restore /path/to/file.db</code></td><td>Restore from a specific path</td></tr>
    <tr><td><code>logbook import-db /path/to/file.db</code></td><td>Import a database file (alias for restore)</td></tr>
  </table>

  <h3>Configuration &amp; service</h3>
  <table>
    <tr><td><code>logbook config</code></td><td>Show current configuration</td></tr>
    <tr><td><code>logbook config-set &lt;KEY&gt; &lt;VALUE&gt;</code></td><td>Set a config value (persisted to .env file)</td></tr>
    <tr><td><code>logbook doctor</code></td><td>Check installation health (runtime, service, database, network)</td></tr>
    <tr><td><code>logbook install-service</code></td><td>Install as system service (systemd on Linux, launchd on macOS)</td></tr>
    <tr><td><code>logbook restart</code></td><td>Reinstall package and restart service</td></tr>
  </table>
  <p>All data commands support <code>--json</code> for machine-readable output.</p>

  <h2>Git metadata</h2>
  <p>When logging work tied to commits, include git info:</p>
  <pre>logbook log "shipped the auth refactor" --project &lt;ID&gt; --commit abc1234 --repo logbook --branch master</pre>
  <p>Multiple <code>--commit</code> flags attach multiple commits to one entry. Git metadata is stored as:</p>
  <pre>{"git": {"repo": "logbook", "branch": "master", "commits": ["abc1234", "def5678"]}}</pre>

  <h2>Claude Code integration</h2>
  <p>Connect once with:</p>
  <pre>claude mcp add logbook -s user -e LOGBOOK_URL=http://localhost:8000 -- logbook-mcp</pre>
  <p>Then just talk naturally — "What's on my plate?", "Log that we finished the refactor", "What did I do last week?"</p>

  <h2>How information is organized</h2>
  <dl>
    <dt>Projects</dt>
    <dd>Top-level containers for related work. Each has an optional motivation field.</dd>
    <dt>Goals</dt>
    <dd>Milestones within a project (e.g. "Ship v1"). Optional motivation and target date.</dd>
    <dt>Tasks</dt>
    <dd>Concrete work items with priority (low/medium/high/critical), rationale, and dependencies. A task is "blocked" when it depends on an unfinished task.</dd>
    <dt>Log entries</dt>
    <dd>Timestamped records of work done. Can link to a project and task, and include git commit metadata.</dd>
  </dl>

  <h2>Priorities &amp; next actions</h2>
  <p>The <strong>next</strong> command ranks unblocked tasks by: priority first, then how many other tasks they unblock, then age. Everything it suggests is actionable right now.</p>

  <h2>Data &amp; backups</h2>
  <p>Everything lives in a single <code>logbook.db</code> file. No cloud, no sync. Use <code>logbook backup</code> to create a clean copy, or <code>logbook import-db</code> to restore one.</p>

  <h2>API</h2>
  <p>REST API at <code>http://localhost:8000</code>. OpenAPI docs at <a href="/docs">/docs</a>. All responses use <code>{"data": ..., "meta": ...}</code> envelope.</p>
</div>`;
}

// --- Tab loading ---

async function loadTab(tab) {
  currentTab = tab;

  // Update active tab button
  for (const btn of $$(".tab")) {
    btn.classList.toggle("active", btn.dataset.tab === tab);
  }

  content.innerHTML = `<p class="loading">Loading...</p>`;

  try {
    if (tab === "summary") {
      const summaryData = await api("/summary");
      let archivedProjects = [];
      if (includeArchived) {
        const allProjects = await api("/projects?status=archived");
        const activeIds = new Set((summaryData.active_projects || []).map((p) => p.id));
        archivedProjects = (Array.isArray(allProjects) ? allProjects : []).filter((p) => !activeIds.has(p.id)).map((p) => ({
          id: p.id, name: p.name, motivation: p.motivation || "", status: p.status,
          goals_active: 0, tasks_summary: {}, blocked_tasks: 0,
        }));
      }
      renderSummary(summaryData, archivedProjects);
    } else if (tab === "today") {
      renderToday(await api("/summary/today"));
    } else if (tab === "weekly") {
      renderWeekly(await api(`/summary/weekly?weeks_back=${weeksBack}`));
    } else if (tab === "help") {
      renderHelp();
      return;
    } else if (tab === "api") {
      content.innerHTML = `<iframe src="/docs" class="api-frame"></iframe>`;
      return;
    }
  } catch (err) {
    content.innerHTML = `<p class="error">Failed to load: ${esc(err.message)}</p>`;
  }
}

// --- Search ---

function highlight(snippet) {
  return esc(snippet).replace(/&gt;&gt;&gt;/g, "<mark>").replace(/&lt;&lt;&lt;/g, "</mark>");
}

const TYPE_ORDER = ["project", "goal", "task", "work_log_entry"];
const TYPE_LABELS = {
  project: "Projects",
  goal: "Goals",
  task: "Tasks",
  work_log_entry: "Work log",
};

function renderSearch(data) {
  if (!data.results?.length) {
    content.innerHTML = `<p class="empty">No results for "${esc(data.query)}".</p>`;
    return;
  }

  const grouped = groupBy(data.results, (r) => r.entity_type);

  let html = `<div class="search-header">${data.total} results</div>`;
  for (const type of TYPE_ORDER) {
    const results = grouped[type];
    if (!results) continue;
    html += `<div class="section"><div class="section-title">${TYPE_LABELS[type]}</div>`;
    for (const r of results) {
      const body = r.body_snippet?.trim();
      if (r.entity_type === "work_log_entry") {
        const projPart = r.project_name ? `<span class="search-project">${esc(r.project_name)}</span>` : "";
        const timePart = r.created_at ? time(r.created_at) : "";
        const meta = [projPart, timePart].filter(Boolean).join(" \u00b7 ");
        html += `
          <div class="search-result">
            <div class="search-log-text">${highlight(r.title_snippet)}</div>
            ${meta ? `<div class="item-meta">${meta}</div>` : ""}
          </div>`;
      } else {
        const projectNote = r.project_name ? `<div class="item-meta"><span class="search-project">${esc(r.project_name)}</span></div>` : "";
        html += `
          <div class="search-result">
            <div class="item-title">${highlight(r.title_snippet)}</div>
            ${body && body !== "{}" ? `<div class="item-meta">${highlight(body)}</div>` : ""}
            ${projectNote}
          </div>`;
      }
    }
    html += `</div>`;
  }
  content.innerHTML = html;
}

let searchTimeout = null;

function onSearchInput(e) {
  const query = e.target.value.trim();
  clearTimeout(searchTimeout);

  if (!query) {
    // Clear active tab highlight and reload current tab
    loadTab(currentTab);
    return;
  }

  // Deactivate tab buttons while searching
  for (const btn of $$(".tab")) btn.classList.remove("active");

  searchTimeout = setTimeout(async () => {
    content.innerHTML = `<p class="loading">Searching...</p>`;
    try {
      const data = await api(`/search?q=${encodeURIComponent(query)}&limit=20`);
      renderSearch(data);
    } catch (err) {
      content.innerHTML = `<p class="error">Search failed: ${esc(err.message)}</p>`;
    }
  }, 300);
}

// --- Theme toggle ---

function getSystemTheme() {
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function setTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  $("#theme-toggle").textContent = theme === "dark" ? "\u2600" : "\u263E";
}

// Apply saved theme or follow system
setTheme(localStorage.getItem("logbook-theme") || getSystemTheme());

// Follow system changes when no manual override
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
  if (!localStorage.getItem("logbook-theme")) setTheme(getSystemTheme());
});

$("#theme-toggle").addEventListener("click", () => {
  const current = document.documentElement.getAttribute("data-theme");
  const next = current === "dark" ? "light" : "dark";
  localStorage.setItem("logbook-theme", next);
  setTheme(next);
});

// --- Init ---

for (const btn of $$(".tab")) {
  btn.addEventListener("click", () => {
    $("#search-input").value = "";
    if (btn.dataset.tab === "weekly") weeksBack = 0;
    loadTab(btn.dataset.tab);
  });
}

$("#search-input").addEventListener("input", onSearchInput);

loadTab("summary");
