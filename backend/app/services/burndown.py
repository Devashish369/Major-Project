"""
services/burndown.py – Ideal vs actual remaining-hours series (M9).

Definitions (viva-ready):
  total_hours   = sum of estimate_hours over ALL tasks in the project.
  actual[d]     = total_hours − sum(estimate_hours of tasks whose completed_at
                  date is <= d).  Only computed for days up to today.
  ideal[d]      = straight line from total_hours on the start day to 0 on the
                  end day (project due date).

Start day: project.start_date, else the earliest task created_at, else today.
End day:   project.due_date, else today (so the chart still draws something).
The range is stretched to include today / late completions and capped so a
mistyped date can never produce a huge response.
"""

from datetime import date, datetime, timedelta
from typing import Optional

MAX_DAYS = 366


def _parse(d: Optional[str]) -> Optional[date]:
    if not d:
        return None
    try:
        return date.fromisoformat(d[:10])
    except ValueError:
        return None


def compute_burndown(
    start_date: Optional[str],
    due_date: Optional[str],
    tasks: list[dict],          # [{"estimate_hours", "completed_at": datetime|None, "created_at": datetime|None}]
    today: Optional[date] = None,
) -> dict:
    today = today or date.today()
    total = round(sum((t.get("estimate_hours") or 0) for t in tasks), 2)

    if not tasks or total <= 0:
        return {"total_hours": total, "start": None, "end": None, "points": []}

    created = [t["created_at"].date() for t in tasks if t.get("created_at")]
    start = _parse(start_date) or (min(created) if created else today)
    end = _parse(due_date) or today

    # Completed hours per calendar day
    done_by_day: dict[date, float] = {}
    for t in tasks:
        ca = t.get("completed_at")
        if ca:
            day = ca.date() if isinstance(ca, datetime) else ca
            done_by_day[day] = done_by_day.get(day, 0.0) + (t.get("estimate_hours") or 0)

    # Stretch range so today and every completion day are visible
    if done_by_day:
        start = min(start, min(done_by_day))
        end = max(end, max(done_by_day))
    end = max(end, start)
    if (end - start).days > MAX_DAYS:
        end = start + timedelta(days=MAX_DAYS)

    span = max(1, (end - start).days)
    points = []
    cum_done = sum(h for d, h in done_by_day.items() if d < start)
    for i in range((end - start).days + 1):
        day = start + timedelta(days=i)
        cum_done += done_by_day.get(day, 0.0)
        ideal = max(0.0, total * (1 - i / span))
        points.append({
            "date": day.isoformat(),
            "ideal": round(ideal, 2),
            # No "actual" for the future – the chart line simply stops at today
            "actual": round(max(0.0, total - cum_done), 2) if day <= today else None,
        })

    return {
        "total_hours": total,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "points": points,
    }
