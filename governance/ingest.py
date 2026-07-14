"""Parse an uploaded project-plan workbook into a normalized structure.

The template is not a clean rectangular sheet: a metadata block sits in the
top-left, and the task table starts a few columns over with its header on an
arbitrary row. So we detect both regions by content rather than fixed offsets,
which also makes the parser tolerant of small layout drift between the client's
real plans.

Public API:
    parse_plan(source) -> ParsedPlan     # source: path or file-like (.xlsx)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .plan_spec import (
    CANONICAL_TASK_COLS,
    META_LABELS,
    TASK_HEADER_MATCHERS,
)

_PLACEHOLDER = re.compile(r"^\s*(x+|m+/d+/y+|n/?a|tbd|-+)\s*$", re.I)


class PlanParseError(ValueError):
    """Raised when the workbook does not look like a project plan."""


@dataclass
class ParsedPlan:
    meta: dict
    tasks: pd.DataFrame
    validation: dict = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.meta.get("project_name") or self.meta.get("project_id") or "Untitled project"


def _clean(v):
    """Return a stripped string, or None for blanks/placeholders."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    s = str(v).strip()
    if not s or _PLACEHOLDER.match(s):
        return None
    return s


def _norm(v) -> str:
    s = _clean(v)
    return s.lower().strip() if s else ""


def _to_date(v):
    s = _clean(v)
    if s is None:
        return pd.NaT
    return pd.to_datetime(s, errors="coerce", dayfirst=False)


def _to_pct(v):
    """Coerce %-complete cells (50, '50%', 0.5, '50.0') to a 0-100 float."""
    s = _clean(v)
    if s is None:
        return np.nan
    s = s.replace("%", "").strip()
    try:
        x = float(s)
    except ValueError:
        return np.nan
    if 0 <= x <= 1:            # fraction form
        x *= 100
    return float(np.clip(x, 0, 100))


def _to_bool(v):
    s = _norm(v)
    if s in {"yes", "y", "true", "1", "critical"}:
        return True
    if s in {"no", "n", "false", "0"}:
        return False
    return False


def _find_header_row(raw: pd.DataFrame) -> tuple[int, int]:
    """Locate the task-table header by finding the 'Project Activity' cell."""
    for r in range(min(len(raw), 15)):
        for c in range(raw.shape[1]):
            if _norm(raw.iat[r, c]) in {"project activity", "activity"}:
                return r, c
    raise PlanParseError(
        "Could not find the task table — no 'Project Activity' header. "
        "Is this the project-plan template?"
    )


def _map_columns(raw: pd.DataFrame, header_row: int) -> dict[str, int]:
    """Map canonical field -> column index using the header row's text."""
    headers = {c: _norm(raw.iat[header_row, c]) for c in range(raw.shape[1])}
    mapping: dict[str, int] = {}
    used: set[int] = set()
    for canon, needles in TASK_HEADER_MATCHERS:
        for c, text in headers.items():
            if c in used or not text:
                continue
            if any(n in text for n in needles):
                mapping[canon] = c
                used.add(c)
                break
    if "activity" not in mapping:
        raise PlanParseError("Task table has no activity column.")
    return mapping


def _extract_meta(raw: pd.DataFrame, header_row: int, task_left: int) -> dict:
    """Read the metadata block: labels sit in the columns left of the task table.

    The value is taken from a cell to the right of the label but *before* the
    task table begins, so a blank/placeholder value never bleeds across the gap
    into the first task column (which would otherwise read 'WBS' as an ID).
    """
    meta: dict = {}
    max_row = min(len(raw), header_row + 12)
    label_cols = range(max(1, min(task_left, 3)))
    for r in range(max_row):
        for c in label_cols:
            key = META_LABELS.get(_norm(raw.iat[r, c]))
            if not key or key in meta:
                continue
            for cc in range(c + 1, max(c + 2, task_left)):   # value stays left of the table
                val = _clean(raw.iat[r, cc])
                if val is not None:
                    meta[key] = val
                    break
    for dk in ("planned_go_live", "forecast_go_live"):
        if dk in meta:
            d = pd.to_datetime(meta[dk], errors="coerce")
            meta[dk] = None if pd.isna(d) else d.normalize()
    return meta


def parse_plan(source) -> ParsedPlan:
    """Parse a project-plan .xlsx (path or file-like) into a ParsedPlan."""
    raw = pd.read_excel(source, header=None, dtype=object)
    if raw.empty:
        raise PlanParseError("The workbook is empty.")

    header_row, _ = _find_header_row(raw)
    colmap = _map_columns(raw, header_row)
    task_left = min(colmap.values())
    meta = _extract_meta(raw, header_row, task_left)

    body = raw.iloc[header_row + 1:].reset_index(drop=True)
    out = {canon: body.iloc[:, idx] for canon, idx in colmap.items()}
    df = pd.DataFrame(out)

    # Forward-fill the phase grouping (phase/WBS labels only appear on the first
    # row of each phase block in the template).
    for grp in ("phase", "wbs"):
        if grp in df:
            df[grp] = df[grp].map(_clean).ffill()

    df = df[df["activity"].map(_clean).notna()].reset_index(drop=True)
    if df.empty:
        raise PlanParseError("No task rows found under the header.")

    # Normalize each field.
    df["activity"] = df["activity"].map(_clean)
    df["phase"] = df.get("phase", pd.Series([None] * len(df))).map(_clean)
    df["wbs"] = pd.to_numeric(df.get("wbs"), errors="coerce")
    df["task_id"] = df.get("task_id", pd.Series([None] * len(df))).map(_clean)
    df["owner"] = df.get("owner", pd.Series([None] * len(df))).map(_clean)
    df["team"] = df.get("team", pd.Series([None] * len(df))).map(_clean)
    df["status"] = df.get("status", pd.Series([None] * len(df))).map(_clean)
    df["pct_complete"] = df.get("pct_complete", pd.Series([np.nan] * len(df))).map(_to_pct)
    df["priority"] = df.get("priority", pd.Series([None] * len(df))).map(_clean)
    df["critical_path"] = df.get("critical_path", pd.Series([None] * len(df))).map(_to_bool)
    df["dependency"] = df.get("dependency", pd.Series([None] * len(df))).map(_clean)
    df["risk_level"] = df.get("risk_level", pd.Series([None] * len(df))).map(
        lambda v: (_clean(v) or "").title() or None
    )
    for dc in ("planned_start", "actual_start", "planned_finish", "actual_finish"):
        df[dc] = df.get(dc, pd.Series([None] * len(df))).map(_to_date)

    df = df.reindex(columns=CANONICAL_TASK_COLS)

    validation = _validate(meta, df, colmap)
    return ParsedPlan(meta=meta, tasks=df, validation=validation)


def _validate(meta: dict, df: pd.DataFrame, colmap: dict) -> dict:
    """Produce a human-facing validation report for the ingestion screen."""
    n = len(df)
    filled = {
        "owner": int(df["owner"].notna().sum()),
        "status": int(df["status"].notna().sum()),
        "pct_complete": int(df["pct_complete"].notna().sum()),
        "risk_level": int(df["risk_level"].notna().sum()),
        "planned_finish": int(df["planned_finish"].notna().sum()),
    }
    issues: list[str] = []
    if not meta.get("project_name"):
        issues.append("Project Name is blank in the metadata block.")
    if not meta.get("planned_go_live"):
        issues.append("Planned Go-Live Date is missing or unparseable.")
    if not meta.get("forecast_go_live"):
        issues.append("Forecast Go-Live Date is missing — schedule variance cannot be measured.")
    if filled["status"] == 0:
        issues.append("No task Status values — completion and phase can't be inferred.")
    if filled["pct_complete"] == 0:
        issues.append("No % Complete values — progress will read as 0%.")
    coverage = round(100 * sum(filled.values()) / (len(filled) * n)) if n else 0
    return {
        "task_count": n,
        "phase_count": int(df["phase"].nunique(dropna=True)),
        "columns_detected": list(colmap.keys()),
        "fill": filled,
        "coverage_pct": coverage,
        "issues": issues,
        "ok": len(issues) == 0,
    }
