"""
services/skill_gaps.py – skills the open work needs but NOBODY on the team has, and who should
learn each one.

For every required skill of an open task that no member has (level ≥ 1, after synonyms):
  closest       the member whose existing skills are most related to the missing one:
                    readiness = relatedness(missing, their skill) × (0.5 + 0.5 × level / 5)
                taking their best skill; needs relatedness ≥ 0.3, otherwise nobody is "close".
                Ties: lower workload, then better on-time rate.
                e.g. missing "generative ai": a member with RAG level 4 → 0.9 × 0.9 = 0.81,
                a member with React level 5 → 0 (unrelated)  →  the RAG member is suggested.
  least_loaded  the member with the lowest workload (same utilisation as the Team tab bars),
                ties broken by on-time rate – the person with the most time to learn.
If both are the same person, the suggestion says so.  Nothing is written to the database.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.skills import canonical, canonical_levels, relatedness

MIN_RELATEDNESS = 0.3


@dataclass
class GapMember:
    user_id: int
    full_name: str
    skills: dict          # raw {name: level}
    utilization: float    # open hours / capacity (Team tab)
    on_time_rate: float


def compute_skill_gaps(tasks: list[dict], members: list[GapMember]) -> list[dict]:
    """
    tasks: open tasks as {"id", "number", "title", "required_skills": [...]}
    Returns one entry per missing skill, most-needed first.
    """
    if not members:
        return []
    levels = {m.user_id: canonical_levels(m.skills) for m in members}
    team_has = {s for lv in levels.values() for s, n in lv.items() if n >= 1}

    needed: dict[str, list[dict]] = {}
    shown_name: dict[str, str] = {}
    for t in tasks:
        for raw in t.get("required_skills") or []:
            skill = canonical(raw)
            if not skill or skill in team_has:
                continue
            shown_name.setdefault(skill, str(raw).strip())
            refs = needed.setdefault(skill, [])
            if all(r["id"] != t["id"] for r in refs):
                refs.append({"id": t["id"], "number": t.get("number") or t["id"], "title": t["title"]})

    least = min(members, key=lambda m: (m.utilization, -m.on_time_rate, m.user_id))
    gaps = []
    for skill, refs in needed.items():
        best = None    # (readiness, -utilization, on_time, member, via_skill, via_level, relatedness)
        for m in members:
            for have, level in levels[m.user_id].items():
                rel = relatedness(skill, have)
                if rel < MIN_RELATEDNESS:
                    continue
                readiness = rel * (0.5 + 0.5 * min(level, 5) / 5)
                cand = (round(readiness, 4), -m.utilization, m.on_time_rate, -m.user_id)
                if best is None or cand > best[0]:
                    best = (cand, m, have, level, rel)

        closest = None
        if best:
            (readiness, *_), m, have, level, rel = best
            closest = {"user_id": m.user_id, "full_name": m.full_name, "via_skill": have,
                       "via_level": level, "relatedness": rel, "readiness": readiness,
                       "utilization": round(m.utilization, 4)}
        least_out = {"user_id": least.user_id, "full_name": least.full_name,
                     "utilization": round(least.utilization, 4)}

        name = shown_name[skill]
        n = len(refs)
        tasks_txt = f"{n} open task{'s' if n > 1 else ''} need{'s' if n == 1 else ''} {name}"
        if closest and closest["user_id"] == least.user_id:
            advice = (f"{closest['full_name']} should learn {name}: their {closest['via_skill']} skill "
                      f"(level {closest['via_level']}) is the closest match and they have the lowest workload "
                      f"({round(least.utilization * 100)} %).")
        elif closest:
            advice = (f"{closest['full_name']} is the fastest learner for {name} (knows {closest['via_skill']}, "
                      f"level {closest['via_level']}, {round(closest['relatedness'] * 100)} % related); "
                      f"{least.full_name} has the most free time ({round(least.utilization * 100)} % workload).")
        else:
            advice = (f"No one has a related skill. {least.full_name} has the lowest workload "
                      f"({round(least.utilization * 100)} %) and could learn {name}, or bring in someone who knows it.")
        gaps.append({"skill": name, "canonical": skill, "tasks": refs, "closest": closest,
                     "least_loaded": least_out, "summary": f"No one on the team has {name}: {tasks_txt}.",
                     "advice": advice})

    gaps.sort(key=lambda g: (-len(g["tasks"]), g["canonical"]))
    return gaps
