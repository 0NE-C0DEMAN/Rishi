"""Adapter for Microsoft Planner / Project task exports.

A second plan layout the client sends. It looks nothing like the WBS template:

  * a small metadata block in the first column (Project name, Plan owner,
    Project start/finish date, Duration, % complete, Exported on);
  * a task header row further down, then one row per task;
  * an ``Outline number`` (1, 1.1, 1.1.2 ...) encoding a hierarchy, where the
    top level is the delivery phase and only the leaves are real work;
  * ``% complete`` as a 0-1 fraction rather than a percentage;
  * effort expressed as text ("5545 hours"), split into total, completed and
    remaining — the only quantitative basis either format gives us for cost.

The adapter emits exactly the canonical task frame the WBS parser produces, so
everything downstream (metrics, budget, the dashboard) is format-agnostic.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from .plan_spec import CANONICAL_TASK_COLS

# Header cells that identify this layout.
SIGNATURE = {"outline number", "task number"}

_META_LABELS = {
    "project name": "project_name",
    "plan owner": "owner",
    "project start date": "project_start",
    "project finish date": "planned_go_live",
    "duration": "duration",
    "% complete": "pct_complete",
    "exported on": "exported_on",
}

_COLUMNS = {
    "task number": "task_id",
    "outline number": "outline",
    "name": "activity",
    "team | resource": "team",
    "assigned to": "owner",
    "assigned to (text)": "owner_text",
    "start": "planned_start",
    "finish": "planned_finish",
    "% complete": "pct_complete",
    "duration": "duration",
    "depends on": "dependency",
    "effort": "effort",
    "effort completed": "effort_completed",
    "effort remaining": "effort_remaining",
    "milestone": "milestone",
    "priority": "priority",
    "bucket": "bucket",
    "notes": "notes",
}


def _txt(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    s = str(v).strip()
    return s or None


def _hours(v):
    """'5545 hours' -> 5545.0 ; blank -> NaN."""
    s = _txt(v)
    if not s:
        return np.nan
    m = re.search(r"([\d,]+(?:\.\d+)?)", s)
    if not m:
        return np.nan
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return np.nan


def _pct(v):
    """Planner stores 0-1; the rest of the app works in 0-100."""
    if v is None or (isinstance(v, str) and not v.strip()):
        return np.nan
    try:
        x = float(v)
    except (TypeError, ValueError):
        return np.nan
    if np.isnan(x):
        return np.nan
    if 0 <= x <= 1:
        x *= 100
    return float(np.clip(x, 0, 100))


def looks_like_planner(raw: pd.DataFrame) -> tuple[bool, int]:
    """Detect the layout and return (matched, header_row_index)."""
    for r in range(min(len(raw), 30)):
        cells = {str(raw.iat[r, c]).strip().lower() for c in range(raw.shape[1])}
        if SIGNATURE <= cells:
            return True, r
    return False, -1


def parse(raw: pd.DataFrame, header_row: int):
    """Return (meta, tasks_dataframe) from a Planner export."""
    # --- metadata block above the header ---------------------------------
    meta: dict = {}
    for r in range(header_row):
        label = str(raw.iat[r, 0]).strip().lower() if raw.shape[1] else ""
        key = _META_LABELS.get(label)
        if not key or key in meta:
            continue
        for c in range(1, raw.shape[1]):
            val = _txt(raw.iat[r, c])
            if val is not None:
                meta[key] = val
                break

    for dk in ("project_start", "planned_go_live"):
        if dk in meta:
            d = pd.to_datetime(meta[dk], errors="coerce")
            meta[dk] = None if pd.isna(d) else d.normalize()
    if "pct_complete" in meta:
        meta["pct_complete"] = _pct(meta["pct_complete"])

    # --- task table -------------------------------------------------------
    headers = [str(raw.iat[header_row, c]).strip().lower() for c in range(raw.shape[1])]
    body = raw.iloc[header_row + 1:].reset_index(drop=True)
    cols = {}
    for idx, h in enumerate(headers):
        canon = _COLUMNS.get(h)
        if canon and canon not in cols:
            cols[canon] = body.iloc[:, idx]
    df = pd.DataFrame(cols)
    df = df[df.get("activity").map(_txt).notna()].reset_index(drop=True)
    if df.empty:
        return meta, df

    # --- hierarchy: level 1 is the phase; only leaves are real work -------
    outline = df["outline"].map(lambda v: str(_txt(v) or ""))
    level = outline.map(lambda s: s.count(".") + 1 if s else 1)
    root = outline.map(lambda s: s.split(".")[0] if s else "")
    names = df["activity"].map(_txt)

    phase_by_root = {}
    for i, lv in enumerate(level):
        if lv == 1 and root.iat[i] not in phase_by_root:
            phase_by_root[root.iat[i]] = names.iat[i]

    # a row is a summary row when another row's outline extends it
    prefixes = {o.rsplit(".", 1)[0] for o in outline if "." in o}
    is_leaf = ~outline.isin(prefixes)

    out = pd.DataFrame(index=df.index)
    out["wbs"] = pd.to_numeric(root, errors="coerce")
    out["phase"] = root.map(phase_by_root)
    out["task_id"] = df.get("task_id").map(_txt) if "task_id" in df else None
    out["activity"] = names
    out["owner"] = (df.get("owner").map(_txt) if "owner" in df else None)
    if "owner_text" in df:
        out["owner"] = out["owner"].fillna(df["owner_text"].map(_txt))
    out["team"] = df.get("team").map(_txt) if "team" in df else None
    out["pct_complete"] = df["pct_complete"].map(_pct) if "pct_complete" in df else np.nan
    out["priority"] = df.get("priority").map(_txt) if "priority" in df else None

    # Planner has no risk column; a milestone is the closest thing to a gate.
    ms = df.get("milestone").map(lambda v: str(_txt(v) or "").lower() in {"yes", "true", "1"}) if "milestone" in df else False
    out["critical_path"] = ms
    out["dependency"] = df.get("dependency").map(_txt) if "dependency" in df else None
    out["risk_level"] = None

    for src, dst in (("planned_start", "planned_start"), ("planned_finish", "planned_finish")):
        out[dst] = pd.to_datetime(df[src], errors="coerce") if src in df else pd.NaT

    # Status is implied by completion; actuals follow from it so the schedule
    # maths downstream behaves the same as for the WBS format.
    def _status(p):
        if pd.isna(p):
            return None
        if p >= 99.999:
            return "Complete"
        if p <= 0:
            return "Not Started"
        return "In Progress"

    out["status"] = out["pct_complete"].map(_status)
    started = out["pct_complete"].fillna(0) > 0
    done = out["status"].eq("Complete")
    out["actual_start"] = out["planned_start"].where(started)
    out["actual_finish"] = out["planned_finish"].where(done)

    # effort (hours) — carried through for the budget model
    for c in ("effort", "effort_completed", "effort_remaining"):
        out[c] = df[c].map(_hours) if c in df else np.nan

    out["is_leaf"] = is_leaf.values
    out["level"] = level.values

    # Summary rows are roll-ups of their children; keeping them would double
    # count every effort hour and every task in the portfolio metrics.
    leaves = out[out["is_leaf"]].copy()
    if leaves.empty:
        leaves = out.copy()

    cols_out = CANONICAL_TASK_COLS + ["effort", "effort_completed", "effort_remaining"]
    leaves = leaves.reindex(columns=cols_out)
    return meta, leaves.reset_index(drop=True)
