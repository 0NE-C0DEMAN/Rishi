"""Generate realistic, filled sample project plans in the template layout.

The client's real template ships blank (placeholder cells only), so a demo needs
plausible data to show a populated executive dashboard. Each generated workbook
is one project with a distinct health profile (on-track / slipping / at-risk),
mirroring the template's layout closely enough that the ingest parser treats it
exactly like a real upload.

Run:  python -m governance.samples      # writes data/samples/*.xlsx
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta
from pathlib import Path

from openpyxl import Workbook

from .plan_spec import PHASES

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "data" / "samples"

_TASK_HEADERS = [
    "WBS", "Phase", "Task ID", "Project Activity", "Owner", "Team", "Status",
    "% Complete", "Priority", "Critical path (Yes/No)",
    "Dependency (If any / Predecessors)",
    "Risk Level (Low / Medium / High / Critical)",
    "Planned Start Date", "Actual Start Date", "Planned Finish Date",
    "Actual Finish date",
    "Effort (hours)", "Effort completed (hours)", "Effort remaining (hours)",
]
_HDR_COL0 = 3   # task table starts at column D (0-based index 3)

_CRIT_KEYWORDS = (
    "sign-off", "sign off", "go no go", "readiness", "production deployment",
    "architecture review", "uat", "cutover", "charter",
)


def _flat_tasks() -> list[tuple[int, str, str]]:
    """(wbs, phase, activity) for all 40 activities, in delivery order."""
    out = []
    for wbs, phase, acts in PHASES:
        for a in acts:
            out.append((wbs, phase, a))
    return out


def _profiles() -> list[dict]:
    today = datetime(2026, 7, 9)
    return [
        dict(
            project_id="PRJ-1042", name="Atlas ERP Migration",
            owner="D. Whitfield", stakeholder="Finance Transformation",
            pm="R. Mendes", team_pool=["Platform", "Apps", "Integration", "PMO"],
            start=datetime(2026, 2, 2), go_live=datetime(2026, 9, 15),
            slip_days=0, front=0.62,
            risks={"Medium": 4, "High": 1, "Critical": 0}, blocked=0,
            approved_budget=150_000,
        ),
        dict(
            project_id="PRJ-1077", name="Orion CRM Rollout",
            owner="S. Adeyemi", stakeholder="Commercial Sales",
            pm="L. Zhou", team_pool=["Apps", "Integration", "QA", "PMO"],
            start=datetime(2026, 1, 12), go_live=datetime(2026, 8, 20),
            slip_days=12, front=0.46,
            risks={"Medium": 5, "High": 3, "Critical": 0}, blocked=1,
            approved_budget=150_000,
        ),
        dict(
            project_id="PRJ-1108", name="Helios Data Platform",
            owner="M. Rossi", stakeholder="Enterprise Data Office",
            pm="K. Nair", team_pool=["Data", "Platform", "Security", "QA"],
            start=datetime(2026, 3, 2), go_live=datetime(2026, 10, 10),
            slip_days=28, front=0.30,
            risks={"Medium": 5, "High": 4, "Critical": 2}, blocked=2,
            today=today, heavy_tail=True,
            # Approved on an optimistic early estimate; the heavy remaining
            # work is what pushes this one through its ceiling.
            approved_budget=210_000,
        ),
        dict(
            project_id="PRJ-0994", name="Vega Payments Integration",
            owner="A. Fischer", stakeholder="Payments & Treasury",
            pm="R. Mendes", team_pool=["Integration", "Security", "Platform", "QA"],
            start=datetime(2025, 11, 10), go_live=datetime(2026, 7, 25),
            slip_days=4, front=0.80,
            risks={"Medium": 3, "High": 1, "Critical": 0}, blocked=0,
            approved_budget=185_000,
        ),
    ]


def _owner_names(pm: str) -> list[str]:
    pool = ["J. Park", "A. Silva", "N. Kaur", "T. Bauer", "E. Novak",
            "H. Costa", "P. Ahmed", "C. Meyer", "V. Rao", "F. Lindqvist"]
    random.shuffle(pool)
    return pool[:6] + [pm]


def _build_rows(p: dict) -> list[list]:
    rng = random.Random(hash(p["project_id"]) & 0xFFFF)
    tasks = _flat_tasks()
    n = len(tasks)
    span = (p["go_live"] - p["start"]).days
    front_idx = int(round(p["front"] * n))
    owners = _owner_names(p["pm"])

    # pre-pick which tasks carry elevated risk / are blocked
    idxs = list(range(n))
    rng.shuffle(idxs)
    risk_assign: dict[int, str] = {}
    cursor = 0
    for level, cnt in (("Critical", p["risks"].get("Critical", 0)),
                       ("High", p["risks"].get("High", 0)),
                       ("Medium", p["risks"].get("Medium", 0))):
        for _ in range(cnt):
            if cursor < len(idxs):
                risk_assign[idxs[cursor]] = level
                cursor += 1
    blocked_set = set(range(max(0, front_idx - 2), front_idx)) if p["blocked"] else set()
    blocked_set = set(list(blocked_set)[: p["blocked"]])

    rows = []
    prev_phase = None
    for i, (wbs, phase, act) in enumerate(tasks):
        ps = p["start"] + timedelta(days=span * i / n * 0.96)
        pf = ps + timedelta(days=max(2, span / n * 1.5))
        low = act.lower()
        crit = "Yes" if any(k in low for k in _CRIT_KEYWORDS) else "No"

        if i in blocked_set:
            status, pct = "Blocked", rng.randint(10, 40)
        elif i < front_idx:
            status, pct = "Complete", 100
        elif i == front_idx:
            status, pct = "In Progress", rng.randint(25, 70)
        else:
            status, pct = "Not Started", 0

        # actuals: filled once a task has started; slip ramps toward the front
        a_start = a_finish = None
        ramp = (i + 1) / max(front_idx, 1)
        slip = timedelta(days=p["slip_days"] * min(ramp, 1) * rng.uniform(0.5, 1.2))
        if status == "Complete":
            a_start = ps + timedelta(days=rng.uniform(-1, 3))
            a_finish = pf + slip
        elif status in ("In Progress", "Blocked"):
            a_start = ps + timedelta(days=rng.uniform(-1, 4))

        risk = risk_assign.get(i, "Low")
        pri = "High" if (crit == "Yes" or risk in ("High", "Critical")) else rng.choice(["Medium", "Low", "Medium"])

        # phase label only on the first row of each phase block (like the template)
        phase_cell = phase if phase != prev_phase else None
        wbs_cell = wbs if phase != prev_phase else None
        prev_phase = phase

        # Invented effort. Later phases carry heavier tasks, and one profile
        # loads its remaining work so the cost forecast breaches before the end.
        base = rng.choice([16, 24, 32, 40, 60, 80])
        if p.get("heavy_tail") and i >= front_idx:
            base *= rng.choice([3, 4, 5])
        if crit == "Yes":
            base = int(base * 1.4)
        effort = int(base)
        done_h = int(round(effort * pct / 100.0))
        left_h = max(0, effort - done_h)

        rows.append([
            wbs_cell, phase_cell, f"{wbs}.{(i % 9) + 1}", act,
            owners[i % len(owners)], rng.choice(p["team_pool"]), status, pct,
            pri, crit, "", risk,
            ps.strftime("%Y-%m-%d"),
            a_start.strftime("%Y-%m-%d") if a_start else "",
            pf.strftime("%Y-%m-%d"),
            a_finish.strftime("%Y-%m-%d") if a_finish else "",
            effort, done_h, left_h,
        ])
    return rows


def _write_workbook(p: dict, path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Project Plan"

    forecast = p["go_live"] + timedelta(days=p["slip_days"])
    meta = [
        (1, "Project ID", p["project_id"]),
        (2, "Project Name", p["name"]),
        (4, "Planned Go Live Date", p["go_live"].strftime("%Y-%m-%d")),
        (5, "Forcast Go Live Date", forecast.strftime("%Y-%m-%d")),
        (7, "Project Owner", p["owner"]),
        (8, "Business Stakeholder", p["stakeholder"]),
        (9, "Project Manager", p["pm"]),
        (11, "Approved Budget", p.get("approved_budget", "")),
    ]
    for r, label, val in meta:
        ws.cell(row=r, column=1, value=label)
        ws.cell(row=r, column=2, value=val)

    for j, h in enumerate(_TASK_HEADERS):          # header row = excel row 1
        ws.cell(row=1, column=_HDR_COL0 + 1 + j, value=h)

    for r, row in enumerate(_build_rows(p), start=2):   # task rows from excel row 2
        for j, val in enumerate(row):
            if val != "" and val is not None:
                ws.cell(row=r, column=_HDR_COL0 + 1 + j, value=val)

    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


def generate(out_dir: Path = SAMPLE_DIR) -> list[Path]:
    paths = []
    for p in _profiles():
        fname = p["name"].lower().replace(" ", "_") + ".xlsx"
        fp = out_dir / fname
        _write_workbook(p, fp)
        paths.append(fp)
    return paths


if __name__ == "__main__":
    for fp in generate():
        print("wrote", fp)
