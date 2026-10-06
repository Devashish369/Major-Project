"""tests/test_seed_data.py – sanity checks on the M10 demo-data definitions (no DB)."""
from seed.demo_projects import PROJECTS, USERS
from seed.seed_demo import _parse_tasks

VALID_LEVELS = {"Low risk", "Medium risk", "High risk"}


def test_twelve_users_and_sixteen_projects():
    assert len(USERS) == 12 and len(PROJECTS) == 16
    assert len({p["title"] for p in PROJECTS}) == 16


def test_each_project_has_8_to_30_valid_tasks():
    known = {s for _, skills, _ in USERS.values() for s in skills}
    for p in PROJECTS:
        tasks = _parse_tasks(p["tasks"])
        assert 8 <= len(tasks) <= 30, p["title"]
        for t in tasks:
            assert t["est"] > 0 and t["title"]
            assert set(t["skills"]) <= known, (p["title"], t["skills"])


def test_teams_decisions_and_expectations_reference_real_people():
    for p in PROJECTS:
        keys = {k for k, _, _ in p["team"]}
        assert keys <= set(USERS) and sum(r == "admin" for _, r, _ in p["team"]) == 1
        assert p["expect"][0] in VALID_LEVELS
        n = len(_parse_tasks(p["tasks"]))
        for _title, _dec, _why, by, idx, _days in p["decisions"]:
            assert by in USERS and (idx is None or 0 <= idx < n)
