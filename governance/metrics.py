"""Governance intelligence: turn normalized plans into executive metrics.

For each project we derive the portfolio fields the client asked for — current
phase, % complete, health (RAG), risk score, planned/forecast go-live, schedule
variance, owner — plus the datasets behind the dashboard's tabs (risk register,
go-live outlook, resource load, milestones). Everything returned here is plain
JSON-serializable Python so the UI layer can render it directly.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .ingest import ParsedPlan
from .plan_spec import (
    MILESTONE_KEYWORDS,
    PHASE_ORDER,
    STATUS_BLOCKED,
    STATUS_DONE,
)

_RISK_WEIGHT = {"Low": 0.15, "Medium": 0.35, "High": 0.70, "Critical": 1.0}
RAG_ORDER = {"Red": 0, "Amber": 1, "Green": 2}


# --------------------------------------------------------------------------- #
# small coercion helpers (numpy/Timestamp -> plain python)
# --------------------------------------------------------------------------- #
def _d(ts) -> str | None:
    if ts is None or pd.isna(ts):
        return None
    return pd.Timestamp(ts).strftime("%Y-%m-%d")


def _i(x) -> int:
    return int(x) if x is not None and not pd.isna(x) else 0


def _status(s) -> str:
    return (s or "").strip().lower()


def _is_done(s) -> bool:
    return _status(s) in STATUS_DONE


def _is_blocked(s) -> bool:
    return _status(s) in STATUS_BLOCKED


def _eff_pct(row) -> float:
    if _is_done(row.status):
        return 100.0
    if pd.notna(row.pct_complete):
        return float(row.pct_complete)
    return 0.0


# --------------------------------------------------------------------------- #
# per-project computation
# --------------------------------------------------------------------------- #
def compute_project(plan: ParsedPlan, today: pd.Timestamp | None = None) -> dict:
    today = pd.Timestamp(today).normalize() if today is not None else pd.Timestamp.now().normalize()
    t = plan.tasks
    meta = plan.meta
    n = len(t)

    eff = t.apply(_eff_pct, axis=1)
    overall_pct = round(float(eff.mean()), 1) if n else 0.0

    done = int(t["status"].map(_is_done).sum())
    blocked = int(t["status"].map(_is_blocked).sum())
    active = int(t["status"].map(lambda s: _status(s) in {"in progress", "in-progress", "ongoing", "wip", "started"}).sum())
    not_started = n - done - blocked - active

    risk_counts = {lvl: int((t["risk_level"] == lvl).sum()) for lvl in ("Medium", "High", "Critical")}
    crit, high, med = risk_counts["Critical"], risk_counts["High"], risk_counts["Medium"]

    # current phase = earliest phase (delivery order) not fully complete
    current_phase = _current_phase(t, eff)

    planned = meta.get("planned_go_live")
    forecast = meta.get("forecast_go_live")
    variance = _schedule_variance(t, planned, forecast)

    # expected progress by elapsed calendar time vs actual
    starts = t["planned_start"].dropna()
    proj_start = starts.min() if not starts.empty else None
    expected_pct = _expected_pct(proj_start, planned, today)
    behind = max(0.0, expected_pct - overall_pct)

    risk_score = _risk_score(variance, med, high, crit, blocked, n, behind)
    rag = _rag(risk_score, variance, crit, high, blocked)

    owner = meta.get("owner") or _mode(t["owner"])

    return {
        "project_id": meta.get("project_id") or plan.name,
        "name": plan.name,
        "owner": owner,
        "pm": meta.get("pm"),
        "stakeholder": meta.get("stakeholder"),
        "phase": current_phase,
        "pct_complete": overall_pct,
        "expected_pct": round(expected_pct, 1),
        "rag": rag,
        "risk_score": risk_score,
        "planned_go_live": _d(planned),
        "forecast_go_live": _d(forecast),
        "schedule_variance_days": variance,
        "task_count": n,
        "tasks_done": done,
        "tasks_active": active,
        "tasks_blocked": blocked,
        "tasks_not_started": not_started,
        "risk_counts": risk_counts,
        "phases": _phase_rollup(t),
    }


def _current_phase(t: pd.DataFrame, eff: pd.Series) -> str:
    present = [p for p in PHASE_ORDER if (t["phase"] == p).any()]
    order = present or PHASE_ORDER
    for phase in order:
        mask = t["phase"] == phase
        if not mask.any():
            continue
        if eff[mask].mean() < 99.9:
            return phase
    return "Closed"


def _schedule_variance(t: pd.DataFrame, planned, forecast) -> int:
    if planned is not None and forecast is not None:
        return int((pd.Timestamp(forecast) - pd.Timestamp(planned)).days)
    # fallback: worst finish slippage among tasks with both dates
    both = t.dropna(subset=["planned_finish", "actual_finish"])
    if not both.empty:
        delta = (both["actual_finish"] - both["planned_finish"]).dt.days
        return int(delta.max())
    return 0


def _expected_pct(proj_start, planned, today) -> float:
    if proj_start is None or planned is None:
        return 0.0
    proj_start, planned = pd.Timestamp(proj_start), pd.Timestamp(planned)
    span = (planned - proj_start).days
    if span <= 0:
        return 100.0
    frac = (today - proj_start).days / span
    return float(np.clip(frac, 0, 1) * 100)


def _risk_score(variance, med, high, crit, blocked, n, behind) -> int:
    r_sched = np.clip(variance / 30.0, 0, 1)
    r_mix = np.clip((0.35 * med + 0.70 * high + 1.0 * crit) / max(0.5 * n, 1), 0, 1)
    r_block = np.clip(blocked / max(0.12 * n, 1), 0, 1)
    r_prog = np.clip(behind / 100.0 * 2.2, 0, 1)
    score = 100 * (0.30 * r_sched + 0.26 * r_mix + 0.14 * r_block + 0.30 * r_prog)
    return int(round(float(np.clip(score, 0, 100))))


def _rag(risk_score, variance, crit, high, blocked) -> str:
    if risk_score >= 60 or variance > 21 or (crit > 0 and blocked > 0):
        return "Red"
    if risk_score >= 38 or variance > 10 or blocked > 1 or crit > 0 or high >= 2:
        return "Amber"
    return "Green"


def _phase_rollup(t: pd.DataFrame) -> list[dict]:
    rows = []
    for phase in PHASE_ORDER:
        mask = t["phase"] == phase
        if not mask.any():
            continue
        sub = t[mask]
        eff = sub.apply(_eff_pct, axis=1)
        rows.append({
            "phase": phase,
            "pct_complete": round(float(eff.mean()), 1),
            "task_count": int(len(sub)),
            "done": int(sub["status"].map(_is_done).sum()),
            "blocked": int(sub["status"].map(_is_blocked).sum()),
        })
    return rows


def _mode(s: pd.Series):
    s = s.dropna()
    return s.mode().iat[0] if not s.empty else None


# --------------------------------------------------------------------------- #
# portfolio-level aggregation + tab datasets
# --------------------------------------------------------------------------- #
def build_portfolio(plans: list[ParsedPlan], today: pd.Timestamp | None = None) -> dict:
    projects = [compute_project(p, today) for p in plans]
    projects.sort(key=lambda p: (RAG_ORDER.get(p["rag"], 3), -p["risk_score"]))

    summary = _summary(projects)
    return {
        "projects": projects,
        "summary": summary,
        "risk_register": _risk_register(plans),
        "go_live": _go_live(projects),
        "resources": _resources(plans),
        "milestones": _milestones(plans, today),
        "generated": _d(pd.Timestamp(today).normalize() if today is not None else pd.Timestamp.now()),
    }


def _summary(projects: list[dict]) -> dict:
    n = len(projects)
    rag = {c: sum(1 for p in projects if p["rag"] == c) for c in ("Red", "Amber", "Green")}
    go_lives = [p["forecast_go_live"] or p["planned_go_live"] for p in projects]
    go_lives = [g for g in go_lives if g]
    return {
        "project_count": n,
        "rag": rag,
        "portfolio_health": ("Red" if rag["Red"] else "Amber" if rag["Amber"] else "Green"),
        "avg_risk": int(round(np.mean([p["risk_score"] for p in projects]))) if n else 0,
        "avg_complete": round(float(np.mean([p["pct_complete"] for p in projects])), 1) if n else 0.0,
        "at_risk": rag["Red"] + rag["Amber"],
        "tasks_total": sum(p["task_count"] for p in projects),
        "tasks_blocked": sum(p["tasks_blocked"] for p in projects),
        "critical_risks": sum(p["risk_counts"]["Critical"] for p in projects),
        "next_go_live": min(go_lives) if go_lives else None,
        "slipping": sum(1 for p in projects if p["schedule_variance_days"] > 0),
    }


def _risk_register(plans: list[ParsedPlan]) -> list[dict]:
    rows = []
    for plan in plans:
        t = plan.tasks
        sub = t[t["risk_level"].isin(["Medium", "High", "Critical"])]
        for _, r in sub.iterrows():
            done = _is_done(r["status"])
            weight = _RISK_WEIGHT.get(r["risk_level"], 0.2)
            rows.append({
                "project": plan.name,
                "phase": r["phase"],
                "activity": r["activity"],
                "owner": r["owner"],
                "risk_level": r["risk_level"],
                "status": r["status"] or "Not Started",
                "planned_finish": _d(r["planned_finish"]),
                "open": not done,
                "exposure": round(weight * (0.3 if done else 1.0), 2),
            })
    rows.sort(key=lambda x: (-x["exposure"], x["project"]))
    return rows


def _go_live(projects: list[dict]) -> list[dict]:
    out = []
    for p in projects:
        v = p["schedule_variance_days"]
        out.append({
            "project": p["name"],
            "planned": p["planned_go_live"],
            "forecast": p["forecast_go_live"],
            "variance_days": v,
            "status": "On track" if v <= 0 else ("At risk" if v > 21 else "Slipping"),
            "rag": p["rag"],
        })
    out.sort(key=lambda x: x["variance_days"], reverse=True)
    return out


def _resources(plans: list[ParsedPlan]) -> dict:
    frames = []
    for plan in plans:
        df = plan.tasks.copy()
        df["project"] = plan.name
        frames.append(df)
    allt = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    def agg(col: str) -> list[dict]:
        if allt.empty or col not in allt:
            return []
        out = []
        for key, sub in allt.dropna(subset=[col]).groupby(col):
            out.append({
                col: key,
                "tasks": int(len(sub)),
                "active": int(sub["status"].map(lambda s: _status(s) in {"in progress", "in-progress", "ongoing"}).sum()),
                "critical_path": int(sub["critical_path"].fillna(False).astype(bool).sum()),
                "open": int((~sub["status"].map(_is_done)).sum()),
            })
        out.sort(key=lambda x: -x["open"])
        return out

    return {"by_owner": agg("owner"), "by_team": agg("team")}


def _milestones(plans: list[ParsedPlan], today) -> list[dict]:
    today = pd.Timestamp(today).normalize() if today is not None else pd.Timestamp.now().normalize()
    rows = []
    for plan in plans:
        t = plan.tasks
        for _, r in t.iterrows():
            act = (r["activity"] or "").lower()
            is_gate = bool(r["critical_path"]) or any(k in act for k in MILESTONE_KEYWORDS)
            if not is_gate:
                continue
            done = _is_done(r["status"])
            pf = r["planned_finish"]
            overdue = bool(pd.notna(pf) and not done and pd.Timestamp(pf) < today)
            rows.append({
                "project": plan.name,
                "phase": r["phase"],
                "milestone": r["activity"],
                "planned_finish": _d(pf),
                "actual_finish": _d(r["actual_finish"]),
                "status": r["status"] or "Not Started",
                "done": done,
                "overdue": overdue,
            })
    rows.sort(key=lambda x: (x["planned_finish"] or "9999"))
    return rows
