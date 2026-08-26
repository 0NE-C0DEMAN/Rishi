"""Cost governance: budget, spend, forecast at completion and cost risk.

Neither plan format carries cost columns, so the figures start from whatever
the plan does give us and stay editable:

  * a Planner export records effort in hours (total / completed / remaining),
    so budget and spend are estimated as effort x a blended day-rate;
  * a WBS plan has no effort, so the estimate falls back to task counts
    weighted by completion;
  * any figure can be overridden per project from the Data page, and an
    override always wins over the estimate.

The maths is standard earned-value:

    EV  (earned value)      = BAC x percent complete
    CPI (cost performance)  = EV / AC
    EAC (forecast at compl) = BAC / CPI          (current efficiency continues)
    Forecast variance       = BAC - EAC          (positive = under budget)

Every returned figure is plain JSON-serializable Python.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Blended cost of a delivery hour. A single, obvious knob: change it here or
# override the resulting budget per project from the Data page.
DEFAULT_HOURLY_RATE = 85.0

# Nominal cost of a task when a plan carries no effort at all, so the WBS
# format still produces a coherent cost picture.
DEFAULT_TASK_COST = 2_400.0


def _f(v, default=np.nan) -> float:
    """Coerce a possibly-dirty override ('12,000', '$12000', '') to a float."""
    if v is None:
        return default
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v) if not (isinstance(v, float) and np.isnan(v)) else default
    s = str(v).strip().replace(",", "").replace("$", "")
    if not s:
        return default
    try:
        return float(s)
    except ValueError:
        return default


def estimate_from_plan(tasks: pd.DataFrame, rate: float = DEFAULT_HOURLY_RATE) -> dict:
    """Derive a budget baseline from the plan itself."""
    total_h = float(pd.to_numeric(tasks.get("effort"), errors="coerce").sum(skipna=True))
    done_h = float(pd.to_numeric(tasks.get("effort_completed"), errors="coerce").sum(skipna=True))
    left_h = float(pd.to_numeric(tasks.get("effort_remaining"), errors="coerce").sum(skipna=True))

    if total_h > 0:
        # Effort-based: the plan tells us the work, we price it.
        return {
            "basis": "effort",
            "hours_total": round(total_h, 1),
            "hours_completed": round(done_h, 1),
            "hours_remaining": round(left_h, 1),
            "approved_budget": round(total_h * rate, 2),
            "actual_spend": round(done_h * rate, 2),
            "eac_hours": round(done_h + left_h, 1) if (done_h or left_h) else round(total_h, 1),
        }

    # No effort anywhere: price the task list and let completion drive spend.
    n = int(len(tasks))
    pct = float(pd.to_numeric(tasks.get("pct_complete"), errors="coerce").fillna(0).mean() or 0)
    bac = n * DEFAULT_TASK_COST
    return {
        "basis": "tasks",
        "hours_total": 0.0, "hours_completed": 0.0, "hours_remaining": 0.0,
        "approved_budget": round(bac, 2),
        "actual_spend": round(bac * pct / 100.0, 2),
        "eac_hours": 0.0,
    }


def task_costs(tasks, rate=DEFAULT_HOURLY_RATE):
    """Allocate budget to each task so cost can be tracked as work lands.

    A task's allocation is its effort priced at the blended rate; where a plan
    carries no effort, every task takes an equal nominal share. Spend to date is
    the allocation earned by its completion, and the balance is what it will
    still cost to finish.
    """
    df = pd.DataFrame(index=tasks.index)
    df["activity"] = tasks.get("activity")
    df["phase"] = tasks.get("phase")
    df["owner"] = tasks.get("owner")
    df["status"] = tasks.get("status")
    df["date"] = pd.to_datetime(tasks.get("planned_finish"), errors="coerce")

    pct = pd.to_numeric(tasks.get("pct_complete"), errors="coerce").fillna(0).clip(0, 100)
    df["pct_complete"] = pct

    hours = pd.to_numeric(tasks.get("effort"), errors="coerce")
    if hours.notna().any() and float(hours.sum(skipna=True)) > 0:
        df["allocated"] = hours.fillna(0) * rate
    else:
        df["allocated"] = float(DEFAULT_TASK_COST)

    done_h = pd.to_numeric(tasks.get("effort_completed"), errors="coerce")
    if done_h.notna().any() and float(done_h.sum(skipna=True)) > 0:
        df["spent"] = done_h.fillna(0) * rate
    else:
        df["spent"] = df["allocated"] * pct / 100.0

    left_h = pd.to_numeric(tasks.get("effort_remaining"), errors="coerce")
    if left_h.notna().any() and float(left_h.sum(skipna=True)) > 0:
        df["to_complete"] = left_h.fillna(0) * rate
    else:
        df["to_complete"] = (df["allocated"] - df["spent"]).clip(lower=0)

    return df


def _breach_point(costs, approved, spent_to_date):
    """Where projected spend crosses the approved budget.

    Remaining work is walked in delivery order, adding each task's cost to a
    running total. The first task that pushes the total past the approved budget
    is the point the programme is forecast to breach, which is what turns a late
    run of heavy tasks into an early warning.
    """
    if approved <= 0:
        return None
    todo = costs[costs["to_complete"] > 0].copy()
    if todo.empty:
        return None
    todo = todo.sort_values("date", na_position="last")
    running = float(spent_to_date)
    for i, (_, row) in enumerate(todo.iterrows(), start=1):
        running += float(row["to_complete"])
        if running > approved:
            return {
                "activity": row["activity"],
                "phase": row["phase"],
                "date": None if pd.isna(row["date"]) else pd.Timestamp(row["date"]).strftime("%Y-%m-%d"),
                "tasks_in": i,
                "tasks_remaining": int(len(todo)),
                "overrun_at_point": round(running - approved, 2),
            }
    return None


def _burn_series(costs, approved, spent_to_date, points=14):
    """Spend to date, then the projected burn across the remaining work."""
    todo = costs[costs["to_complete"] > 0].sort_values("date", na_position="last")
    if todo.empty:
        return []
    running = float(spent_to_date)
    rows = [{"label": "Today", "date": None, "cumulative": round(running, 2),
             "over": running > approved}]
    step = max(1, len(todo) // points)
    for i in range(0, len(todo), step):
        chunk = todo.iloc[i:i + step]
        running += float(chunk["to_complete"].sum())
        d = chunk["date"].dropna()
        rows.append({
            "label": str(chunk.iloc[-1]["phase"] or ""),
            "date": None if d.empty else pd.Timestamp(d.iloc[-1]).strftime("%Y-%m-%d"),
            "cumulative": round(running, 2),
            "over": running > approved,
        })
    return rows


def compute_budget(project: dict, tasks: pd.DataFrame, override: dict | None = None,
                   rate: float = DEFAULT_HOURLY_RATE, meta: dict | None = None) -> dict:
    """All ten cost-governance figures for one project.

    `project` is the output of metrics.compute_project (needs pct_complete and
    schedule_variance_days). `override` may carry any of approved_budget,
    actual_spend or hourly_rate entered by the user.
    """
    override = override or {}
    meta = meta or {}
    rate = _f(override.get("hourly_rate"), rate) or rate
    est = estimate_from_plan(tasks, rate)

    # Precedence: what the user edited, then what the plan states, then the
    # estimate derived from effort. An approved budget is a baseline set before
    # the work is fully known, so it must be able to differ from the estimate —
    # otherwise a forecast breach could never arise.
    bac = _f(override.get("approved_budget"),
             _f(meta.get("approved_budget"), est["approved_budget"]))
    ac = _f(override.get("actual_spend"),
            _f(meta.get("actual_spend"), est["actual_spend"]))
    bac = max(0.0, 0.0 if np.isnan(bac) else bac)
    ac = max(0.0, 0.0 if np.isnan(ac) else ac)

    pct = float(project.get("pct_complete") or 0.0)
    ev = bac * pct / 100.0                       # earned value
    cpi = (ev / ac) if ac > 0 else None          # cost performance index

    utilization = (ac / bac * 100.0) if bac > 0 else 0.0
    remaining = bac - ac

    # Forecast at completion, bottom-up: what has been spent plus what the tasks
    # that are actually left will still cost. That is what lets a run of heavy
    # remaining tasks raise a breach signal early, and equally lets a tail of
    # small tasks confirm the programme is fine.
    costs = task_costs(tasks, rate) if len(tasks) else pd.DataFrame(
        columns=["activity", "phase", "date", "allocated", "spent", "to_complete", "pct_complete"])
    cost_to_complete = float(costs["to_complete"].sum()) if len(costs) else 0.0

    if cost_to_complete > 0:
        eac = ac + cost_to_complete
    elif cpi and cpi > 0:
        eac = bac / cpi
    else:
        eac = bac if pct <= 0 else ac + max(0.0, bac - ev)
    eac = max(0.0, float(eac))

    breach = _breach_point(costs, bac, ac) if len(costs) else None
    burn = _burn_series(costs, bac, ac) if len(costs) else []

    heavy = []
    if len(costs):
        top = costs[costs["to_complete"] > 0].nlargest(5, "to_complete")
        heavy = [{
            "activity": r["activity"], "phase": r["phase"],
            "to_complete": round(float(r["to_complete"]), 2),
            "pct_complete": round(float(r["pct_complete"]), 1),
        } for _, r in top.iterrows()]

    forecast_variance = bac - eac                # positive = under budget
    cost_vs_progress = utilization - pct         # positive = spending ahead of delivery

    health = _budget_health(utilization, pct, forecast_variance, bac, breach is not None)
    score = _cost_risk_score(cost_vs_progress, forecast_variance, bac, cpi,
                             project.get("schedule_variance_days", 0), breach)
    insight = _budget_insight(project, bac, ac, utilization, pct, eac,
                              forecast_variance, cost_vs_progress, cpi, health, breach)

    return {
        "project": project.get("name"),
        "basis": est["basis"],
        "hourly_rate": round(rate, 2),
        "hours_total": est["hours_total"],
        "hours_completed": est["hours_completed"],
        "hours_remaining": est["hours_remaining"],
        "approved_budget": round(bac, 2),
        "actual_spend": round(ac, 2),
        "budget_utilization": round(utilization, 1),
        "remaining_budget": round(remaining, 2),
        "eac": round(eac, 2),
        "forecast_variance": round(forecast_variance, 2),
        "budget_health": health,
        "cost_vs_progress": round(cost_vs_progress, 1),
        "pct_complete": round(pct, 1),
        "cpi": round(cpi, 3) if cpi else None,
        "cost_risk_score": score,
        "budget_insight": insight,
        "cost_to_complete": round(cost_to_complete, 2),
        "projected_breach": breach is not None,
        "breach_point": breach,
        "burn": burn,
        "heavy_remaining": heavy,
        "edited": bool(override),
    }


def _budget_health(utilization: float, pct: float, forecast_variance: float,
                   bac: float, projected_breach: bool = False) -> str:
    """Green on track, Amber watch, Red breach.

    A forecast breach counts even while utilisation still looks comfortable,
    which is the whole point of pricing the remaining tasks.
    """
    over_pct = (-forecast_variance / bac * 100.0) if bac > 0 else 0.0
    drift = utilization - pct
    if over_pct > 10 or drift > 20 or utilization > 100:
        return "Red"
    if projected_breach or over_pct > 2 or drift > 8 or utilization > 90:
        return "Amber"
    return "Green"


def _cost_risk_score(cost_vs_progress: float, forecast_variance: float, bac: float,
                     cpi: float | None, schedule_variance_days: int,
                     breach: dict | None = None) -> int:
    """0-100 assessed risk of exceeding the approved budget."""
    over_pct = (-forecast_variance / bac * 100.0) if bac > 0 else 0.0
    r_over = np.clip(over_pct / 15.0, 0, 1)                       # forecast overrun
    r_drift = np.clip(max(0.0, cost_vs_progress) / 25.0, 0, 1)    # spend ahead of delivery
    r_cpi = np.clip((1.0 - cpi) / 0.35, 0, 1) if cpi else 0.35    # efficiency below 1.0
    r_sched = np.clip(max(0, schedule_variance_days) / 30.0, 0, 1)  # late runs cost more
    score = 100 * (0.38 * r_over + 0.27 * r_drift + 0.20 * r_cpi + 0.15 * r_sched)
    if breach:
        # The earlier in the remaining work the crossing lands, the worse it is.
        share = breach["tasks_in"] / max(breach["tasks_remaining"], 1)
        score = max(score, 55 + 40 * (1 - share))
    return int(round(float(np.clip(score, 0, 100))))


def _money(v: float) -> str:
    a = abs(v)
    if a >= 1_000_000:
        return f"${v/1_000_000:.2f}M"
    if a >= 1_000:
        return f"${v/1_000:.0f}k"
    return f"${v:,.0f}"


def _budget_insight(project, bac, ac, utilization, pct, eac, forecast_variance,
                    cost_vs_progress, cpi, health, breach=None) -> str:
    """Explain the drivers and name a corrective action."""
    name = project.get("name") or "This programme"
    if bac <= 0:
        return "No approved budget is recorded, so cost performance cannot be assessed. Enter the approved budget on the Data page."

    parts = [
        f"{_money(ac)} of {_money(bac)} consumed ({utilization:.0f}%) against {pct:.0f}% delivered."
    ]

    if cost_vs_progress > 8:
        parts.append(
            f"Spend is running {cost_vs_progress:.0f} points ahead of progress"
            + (f", a cost performance index of {cpi:.2f}" if cpi else "")
            + ", so each remaining unit of work is costing more than planned."
        )
    elif cost_vs_progress < -8:
        parts.append(
            f"Delivery is {abs(cost_vs_progress):.0f} points ahead of spend, so the programme is earning value faster than it consumes budget."
        )
    else:
        parts.append("Spend and progress are tracking together.")

    if forecast_variance < 0:
        parts.append(
            f"At the current rate the forecast at completion is {_money(eac)}, "
            f"{_money(-forecast_variance)} over the approved budget."
        )
    else:
        parts.append(
            f"The forecast at completion is {_money(eac)}, leaving {_money(forecast_variance)} of headroom."
        )

    if breach:
        where = breach.get("activity") or "a later task"
        when = f" around {breach['date']}" if breach.get("date") else ""
        parts.append(
            f"On the current run rate the budget is projected to be exhausted at \"{where}\""
            + (f" in {breach['phase']}" if breach.get("phase") else "")
            + f"{when}, with {breach['tasks_remaining'] - breach['tasks_in']} of "
            f"{breach['tasks_remaining']} remaining tasks still unfunded."
        )

    late = int(project.get("schedule_variance_days") or 0)
    if late > 0:
        parts.append(f"The {late}-day schedule slip will carry additional run-rate cost if it is not recovered.")

    if health == "Red":
        action = ("Recommended action: escalate for a budget re-baseline, freeze discretionary scope, "
                  "and re-estimate the remaining work before the next gate.")
    elif health == "Amber":
        action = ("Recommended action: review the remaining-work estimate and tighten change control "
                  "before utilisation passes the approved budget.")
    else:
        action = "Recommended action: maintain current controls and re-check at the next gate."
    parts.append(action)
    return " ".join(parts)


def build_budget(projects: list[dict], plans: list, overrides: dict | None = None,
                 rate: float = DEFAULT_HOURLY_RATE) -> dict:
    """Per-project cost governance plus the portfolio roll-up."""
    overrides = overrides or {}
    by_name = {p.name: p for p in plans}
    rows = []
    for proj in projects:
        plan = by_name.get(proj["name"])
        tasks = plan.tasks if plan is not None else pd.DataFrame()
        rows.append(compute_budget(proj, tasks, overrides.get(proj["name"]), rate,
                                   meta=(plan.meta if plan is not None else None)))

    bac = sum(r["approved_budget"] for r in rows)
    ac = sum(r["actual_spend"] for r in rows)
    eac = sum(r["eac"] for r in rows)
    fv = bac - eac
    worst = max(rows, key=lambda r: r["cost_risk_score"], default=None)
    health_rank = {"Red": 0, "Amber": 1, "Green": 2}
    portfolio_health = min((r["budget_health"] for r in rows),
                           key=lambda h: health_rank.get(h, 3), default="Green")

    return {
        "projects": rows,
        "summary": {
            "approved_budget": round(bac, 2),
            "actual_spend": round(ac, 2),
            "budget_utilization": round(ac / bac * 100, 1) if bac else 0.0,
            "remaining_budget": round(bac - ac, 2),
            "eac": round(eac, 2),
            "forecast_variance": round(fv, 2),
            "budget_health": portfolio_health,
            "over_budget_count": sum(1 for r in rows if r["forecast_variance"] < 0),
            "projected_breach_count": sum(1 for r in rows if r.get("projected_breach")),
            "avg_cost_risk": int(round(float(np.mean([r["cost_risk_score"] for r in rows])))) if rows else 0,
            "worst": worst["project"] if worst else None,
            "hourly_rate": round(rate, 2),
        },
    }
