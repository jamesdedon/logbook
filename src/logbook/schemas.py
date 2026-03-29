from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, field_validator


# --- Response envelope ---

class Meta(BaseModel):
    total: int
    limit: int
    offset: int


class ListResponse(BaseModel):
    data: list[Any]
    meta: Meta


class ItemResponse(BaseModel):
    data: Any


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


# --- Projects ---

class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    motivation: str = ""
    tags: list[str] = []


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    motivation: str | None = None
    status: str | None = None


class ProjectCounts(BaseModel):
    goals: int = 0
    tasks_todo: int = 0
    tasks_in_progress: int = 0
    tasks_done: int = 0
    tasks_cancelled: int = 0


class ProjectOut(BaseModel):
    id: str
    name: str
    description: str
    motivation: str = ""
    status: str
    tags: list[str] = []
    counts: ProjectCounts | None = None
    created_at: str
    updated_at: str


# --- Goals ---

class GoalCreate(BaseModel):
    title: str
    description: str = ""
    motivation: str = ""
    target_date: str | None = None


class GoalUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    motivation: str | None = None
    status: str | None = None
    target_date: str | None = None


class GoalOut(BaseModel):
    id: str
    project_id: str
    title: str
    description: str
    motivation: str = ""
    status: str
    target_date: str | None
    created_at: str
    updated_at: str


# --- Tasks ---

class TaskCreate(BaseModel):
    title: str
    description: str = ""
    rationale: str = ""
    priority: str = "medium"
    goal_id: str | None = None
    tags: list[str] = []
    blocked_by: list[str] = []


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    rationale: str | None = None
    status: str | None = None
    priority: str | None = None
    goal_id: str | None = None


class TaskDepRef(BaseModel):
    id: str
    title: str
    status: str


class LogEntryBrief(BaseModel):
    id: str
    description: str
    created_at: str


class TaskOut(BaseModel):
    id: str
    project_id: str
    project_name: str = ""
    goal_id: str | None
    title: str
    description: str
    rationale: str = ""
    status: str
    priority: str
    tags: list[str] = []
    blocked_by: list[TaskDepRef] = []
    blocks: list[TaskDepRef] = []
    is_blocked: bool = False
    recent_log_entries: list[LogEntryBrief] = []
    created_at: str
    updated_at: str
    completed_at: str | None


class DependencyCreate(BaseModel):
    blocker_id: str


# --- Work Log ---

class WorkLogCreate(BaseModel):
    description: str
    project_id: str | None = None
    task_id: str | None = None
    metadata: dict[str, Any] = {}
    tags: list[str] = []

    @field_validator("metadata", mode="before")
    @classmethod
    def parse_metadata(cls, v: Any) -> dict[str, Any]:
        if isinstance(v, str):
            return json.loads(v)
        return v


class WorkLogUpdate(BaseModel):
    description: str | None = None
    metadata: dict[str, Any] | None = None


class WorkLogOut(BaseModel):
    id: str
    project_id: str | None
    task_id: str | None
    description: str
    metadata: dict[str, Any] = {}
    tags: list[str] = []
    created_at: str


# --- Summary ---

class ProjectSummary(BaseModel):
    id: str
    name: str
    motivation: str = ""
    goals_active: int
    tasks_summary: dict[str, int]
    blocked_tasks: int


class BlockedTaskOut(BaseModel):
    id: str
    title: str
    project_id: str
    blocked_by: list[TaskDepRef]


class NextAction(BaseModel):
    id: str
    title: str
    rationale: str = ""
    priority: str
    project_id: str
    project_name: str


class SummaryOut(BaseModel):
    generated_at: str
    active_projects: list[ProjectSummary]
    recent_activity: list[WorkLogOut]
    blocked_tasks: list[BlockedTaskOut]
    next_actions: list[NextAction]


class TodayOut(BaseModel):
    generated_at: str
    log_entries: list[WorkLogOut]
    tasks_completed: list[TaskOut]


class NextOut(BaseModel):
    generated_at: str
    tasks: list[NextAction]


class ProjectWeekSummary(BaseModel):
    project_id: str
    project_name: str
    project_motivation: str = ""
    entry_count: int
    entries: list[WorkLogOut]


class DaySummary(BaseModel):
    date: str
    entry_count: int
    entries: list[WorkLogOut]


class WeeklyReportOut(BaseModel):
    generated_at: str
    week_start: str
    week_end: str
    total_log_entries: int
    total_tasks_completed: int
    total_tasks_created: int
    total_goals_completed: int
    days: list[DaySummary]
    by_project: list[ProjectWeekSummary]
    tasks_completed: list[TaskOut]
    tasks_created: list[TaskOut]


# --- Search ---

class SearchResult(BaseModel):
    entity_type: str
    entity_id: str
    title_snippet: str
    body_snippet: str
    rank: float
    project_name: str | None = None
    created_at: str | None = None


class SearchResponse(BaseModel):
    query: str
    total: int
    results: list[SearchResult]
