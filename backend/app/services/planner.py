"""
services/planner.py – AI project plan generation (spec §8.1).

Public API:
    generate_plan(description, team_size, duration_weeks)
        → dict with keys: plan (validated Plan), source ("llm" | "fallback")

Flow (spec §8.1):
    1. If USE_CACHED_PLAN_ONLY → load ai/fallback_plan.json (source = "fallback")
    2. Call primary LLM; validate JSON with Pydantic.
       On JSON/validation failure → retry once with same provider.
    3. On second failure → if FALLBACK key is set, call fallback LLM; validate.
    4. On all failures → load ai/fallback_plan.json.

Post-processing (spec §8.1):
    - Clamp estimate_hours to 1–40h
    - Lowercase required_skills
    - Drop depends_on titles that don't match any task title
    - Break dependency cycles (reverse-topo / simple removal)
    - Cap total tasks to 40
"""

import json
import logging
import re
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.config import settings
from app.services.llm import call_llm

logger = logging.getLogger(__name__)

# ── Pydantic schema for the LLM's JSON output (spec §8.1) ────────────────────

class TaskPlan(BaseModel):
    title: str
    description: Optional[str] = None
    module: Optional[str] = None
    priority: Literal["low", "medium", "high", "critical"] = "medium"
    estimate_hours: int = Field(default=8, ge=1, le=40)
    required_skills: list[str] = Field(default_factory=list)
    sprint_index: int = Field(default=0, ge=0)
    depends_on: list[str] = Field(default_factory=list)   # list of task titles

    @field_validator("priority", mode="before")
    @classmethod
    def normalise_priority(cls, v):
        # Accept "MEDIUM" etc from LLM
        return str(v).lower() if isinstance(v, str) else v

    @field_validator("required_skills", mode="before")
    @classmethod
    def lowercase_skills(cls, v):
        if isinstance(v, list):
            return [str(s).lower().strip() for s in v]
        return v

    @field_validator("estimate_hours", mode="before")
    @classmethod
    def clamp_hours(cls, v):
        """Clamp estimate to [1, 40] per spec §8.1."""
        try:
            n = int(float(v))
        except (TypeError, ValueError):
            return 8
        return max(1, min(40, n))


class SprintPlan(BaseModel):
    name: str
    goal: Optional[str] = None


class Plan(BaseModel):
    project_title: str
    summary: Optional[str] = None
    sprints: list[SprintPlan] = Field(default_factory=list)
    tasks: list[TaskPlan] = Field(default_factory=list)

    @model_validator(mode="after")
    def cap_tasks(self):
        """Cap to 40 tasks per spec §8.1."""
        if len(self.tasks) > 40:
            self.tasks = self.tasks[:40]
        return self


# ── Prompt builder ────────────────────────────────────────────────────────────

_SCHEMA = """
Return ONLY a JSON object matching this schema (no markdown):
{
  "project_title": "...",
  "summary": "...",
  "sprints": [{"name": "...", "goal": "..."}],
  "tasks": [
    {
      "title": "...",
      "description": "...",
      "module": "...",
      "priority": "low|medium|high|critical",
      "estimate_hours": <int 1-40>,
      "required_skills": ["skill1", "skill2"],
      "sprint_index": <int, 0-based index into sprints array>,
      "depends_on": ["Task Title A", "Task Title B"]
    }
  ]
}
Rules:
- 3-5 sprints, 8-15 tasks
- depends_on uses exact task titles from the same list
- No cycles in depends_on
- estimate_hours must be an integer between 1 and 40
- required_skills are lowercase strings
"""


def _build_prompt(description: str, team_size: int, duration_weeks: int) -> str:
    return (
        f"Create a software project plan for:\n\n"
        f"Description: {description}\n"
        f"Team size: {team_size} people\n"
        f"Duration: {duration_weeks} weeks\n\n"
        f"{_SCHEMA}"
    )


# ── JSON extraction ───────────────────────────────────────────────────────────

def _extract_json(text: str) -> dict:
    """
    Parse JSON from LLM response.
    The LLM sometimes wraps JSON in ```json ... ``` fences — strip them.
    """
    # Remove markdown code fences if present
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


# ── Post-processing ───────────────────────────────────────────────────────────

def _postprocess(plan: Plan) -> Plan:
    """
    Apply spec §8.1 post-processing rules:
    1. Already done by Pydantic validators: clamp hours, lowercase skills, cap 40.
    2. Drop depends_on titles that don't exist in the task list.
    3. Break dependency cycles using a simple greedy edge-removal.
    """
    titles = {t.title for t in plan.tasks}

    # 1. Drop unknown dependency titles
    for task in plan.tasks:
        task.depends_on = [d for d in task.depends_on if d in titles and d != task.title]

    # 2. Cycle detection & removal (greedy: remove back-edges in DFS)
    #    Build an adjacency map title → [depends_on titles]
    adj: dict[str, list[str]] = {t.title: list(t.depends_on) for t in plan.tasks}
    visiting: set[str] = set()
    visited: set[str] = set()

    def _dfs_remove_cycles(node: str) -> None:
        visiting.add(node)
        new_deps = []
        for dep in adj.get(node, []):
            if dep in visiting:
                # Back edge → cycle; drop this dependency
                logger.warning("Cycle detected: removing %s → %s", node, dep)
                continue
            if dep not in visited:
                _dfs_remove_cycles(dep)
            new_deps.append(dep)
        adj[node] = new_deps
        visiting.discard(node)
        visited.add(node)

    for t in plan.tasks:
        if t.title not in visited:
            _dfs_remove_cycles(t.title)

    for task in plan.tasks:
        task.depends_on = adj.get(task.title, [])

    return plan


# ── Core generate function (spec §8.1) ───────────────────────────────────────

def _parse_plan(raw: str) -> Plan:
    """Parse and validate LLM response into a Plan object."""
    data = _extract_json(raw)
    return Plan.model_validate(data)


def _load_fallback() -> Plan:
    """Load the static fallback plan from disk."""
    path = Path(__file__).parent.parent.parent / "ai" / "fallback_plan.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return Plan.model_validate(data)


def generate_plan(
    description: str,
    team_size: int = 3,
    duration_weeks: int = 8,
) -> dict:
    """
    Generate a project plan.

    Returns:
        {"plan": <Plan dict>, "source": "llm" | "fallback"}

    Never raises — falls back to static JSON instead of crashing the endpoint.
    """
    prompt = _build_prompt(description, team_size, duration_weeks)

    # ── 1. Cached-only mode (spec §8.1) ───────────────────────────────────────
    if settings.USE_CACHED_PLAN_ONLY:
        logger.info("USE_CACHED_PLAN_ONLY=true → loading fallback plan")
        plan = _postprocess(_load_fallback())
        return {"plan": plan.model_dump(), "source": "fallback"}

    # ── 2. Primary LLM (try twice) ────────────────────────────────────────────
    if settings.LLM_API_KEY:
        for attempt in range(2):
            try:
                raw = call_llm(prompt, use_fallback=False)
                plan = _parse_plan(raw)
                plan = _postprocess(plan)
                logger.info("Plan generated by primary LLM (attempt %d)", attempt + 1)
                return {"plan": plan.model_dump(), "source": "llm"}
            except Exception as exc:
                logger.warning("Primary LLM attempt %d failed: %s", attempt + 1, exc)

    # ── 3. Fallback LLM (if key configured) ───────────────────────────────────
    if settings.LLM_FALLBACK_API_KEY:
        for attempt in range(2):
            try:
                raw = call_llm(prompt, use_fallback=True)
                plan = _parse_plan(raw)
                plan = _postprocess(plan)
                logger.info("Plan generated by fallback LLM (attempt %d)", attempt + 1)
                return {"plan": plan.model_dump(), "source": "llm"}
            except Exception as exc:
                logger.warning("Fallback LLM attempt %d failed: %s", attempt + 1, exc)

    # ── 4. Static fallback ─────────────────────────────────────────────────────
    logger.warning("All LLM providers failed — loading static fallback plan")
    plan = _postprocess(_load_fallback())
    return {"plan": plan.model_dump(), "source": "fallback"}
