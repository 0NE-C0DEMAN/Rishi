"""Presentation layer for the executive governance dashboard.

Holds the design system (Meridian palette carried into native Streamlit), the
HTML component builders (KPI cards, RAG pills, styled tables, the workflow
stepper) and the Plotly chart builders. Keeping this out of app.py lets the
orchestration read as a clean sequence of screens.
"""
from __future__ import annotations

import html

import plotly.graph_objects as go

# --------------------------------------------------------------------------- #
# palette (from the approved Meridian design tokens)
# --------------------------------------------------------------------------- #
INK900, INK700, INK500, INK400, INK300 = "#10151D", "#343E4C", "#606B7B", "#8A94A2", "#AAB2BE"
SURFACE, SUNKEN, INSET, BG = "#FFFFFF", "#F5F7FA", "#F0F3F7", "#E9ECF1"
HAIR, HAIR_STRONG = "#E4E8EE", "#D4DAE3"
ACCENT, ACCENT_STRONG, ACCENT_WASH = "#2C58CE", "#1C3C97", "#EAEFFC"
GREEN, GREEN_WASH = "#1A8A5A", "#E5F2EB"
AMBER, AMBER_WASH = "#A9760F", "#FAF0D7"
RED, RED_WASH = "#C0392B", "#F6E7E4"

RAG_COLOR = {"Green": (GREEN, GREEN_WASH), "Amber": (AMBER, AMBER_WASH), "Red": (RED, RED_WASH)}
_MONO = "ui-monospace,'SF Mono',Menlo,Consolas,monospace"
_SANS = "Inter,-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif"


def _esc(v) -> str:
    return html.escape("" if v is None else str(v))


# --------------------------------------------------------------------------- #
# global CSS
# --------------------------------------------------------------------------- #
CSS = f"""
<style>
 #MainMenu, header[data-testid="stHeader"], footer {{display:none !important;}}
 [data-testid="stDecoration"], [data-testid="stStatusWidget"] {{display:none !important;}}
 .stApp {{
   background:
     radial-gradient(1100px 640px at 84% -12%, #EDEFF3, transparent 60%),
     linear-gradient(180deg,#EDEFF3,#E4E8EE);
   background-attachment:fixed;
 }}
 .block-container {{padding:1.1rem 1.6rem 2rem !important; max-width:1500px !important;}}
 html, body, [class*="css"] {{font-family:{_SANS}; color:{INK900};}}
 .eyebrow {{font-family:{_MONO}; font-size:10px; letter-spacing:.16em; text-transform:uppercase;
   color:{INK400}; font-weight:500;}}

 /* topbar */
 .gv-top {{display:flex; align-items:flex-end; justify-content:space-between; gap:16px;
   padding-bottom:14px; margin-bottom:16px; border-bottom:1px solid {HAIR};}}
 .gv-top h1 {{font-size:23px; font-weight:600; letter-spacing:-.012em; margin:5px 0 0; color:{INK900};}}
 .gv-top .sub {{font-size:12.5px; color:{INK500}; margin-top:5px;}}
 .env-pill {{display:inline-flex; align-items:center; gap:8px; padding:6px 11px; border-radius:999px;
   background:{SURFACE}; border:1px solid {HAIR}; box-shadow:0 1px 2px rgba(16,21,29,.05);}}
 .env-dot {{width:6px; height:6px; border-radius:50%; background:{AMBER}; box-shadow:0 0 0 3px {AMBER_WASH};}}
 .env-pill .lab {{font-family:{_MONO}; font-size:10px; letter-spacing:.12em; text-transform:uppercase;
   color:{INK500}; font-weight:500;}}

 /* workflow stepper */
 .stepper {{display:flex; align-items:center; gap:0; margin:2px 0 20px;}}
 .step {{display:flex; align-items:center; gap:9px; padding:8px 15px; border-radius:9px;
   background:{SURFACE}; border:1px solid {HAIR}; box-shadow:0 1px 2px rgba(16,21,29,.04);}}
 .step .n {{width:20px; height:20px; border-radius:50%; display:grid; place-items:center;
   font-family:{_MONO}; font-size:11px; font-weight:600; background:{INSET}; color:{INK400};}}
 .step .t {{font-size:12.5px; color:{INK500}; font-weight:500;}}
 .step.done .n {{background:{GREEN_WASH}; color:{GREEN};}}
 .step.done .t {{color:{INK700};}}
 .step.active {{border-color:{ACCENT}; box-shadow:0 0 0 3px {ACCENT_WASH};}}
 .step.active .n {{background:{ACCENT}; color:#fff;}}
 .step.active .t {{color:{INK900};}}
 .step-sep {{flex:0 0 26px; height:1px; background:{HAIR_STRONG};}}

 /* cards + sections */
 .gv-card {{background:{SURFACE}; border:1px solid {HAIR}; border-radius:12px;
   box-shadow:0 1px 2px rgba(16,21,29,.05); padding:16px 18px;}}
 .sec-head {{display:flex; align-items:baseline; justify-content:space-between; margin:2px 0 12px;}}
 .sec-head h3 {{font-size:15px; font-weight:600; color:{INK900}; margin:0; letter-spacing:-.005em;}}
 .sec-head .meta {{font-family:{_MONO}; font-size:10px; letter-spacing:.1em; text-transform:uppercase; color:{INK400};}}

 /* KPI cards */
 .gv-kpis {{display:grid; grid-template-columns:repeat(6,1fr); gap:12px; margin-bottom:18px;}}
 .kpi {{background:{SURFACE}; border:1px solid {HAIR}; border-radius:11px; padding:14px 15px 12px;
   box-shadow:0 1px 2px rgba(16,21,29,.05);}}
 .kpi .lab {{font-family:{_MONO}; font-size:9.5px; letter-spacing:.12em; text-transform:uppercase;
   color:{INK500}; font-weight:500;}}
 .kpi .val {{font-family:{_MONO}; font-weight:500; color:{INK900}; font-size:27px; line-height:1;
   margin:11px 0 3px; letter-spacing:-.01em;}}
 .kpi .val .u {{font-size:14px; color:{INK400}; font-weight:400; margin-left:2px;}}
 .kpi .foot {{font-family:{_MONO}; font-size:9px; letter-spacing:.06em; text-transform:uppercase; color:{INK300};}}
 .kpi.hl-red {{background:linear-gradient(180deg,{RED_WASH},{SURFACE} 55%);}}
 .kpi.hl-amber {{background:linear-gradient(180deg,{AMBER_WASH},{SURFACE} 60%);}}
 .kpi.hl-green {{background:linear-gradient(180deg,{GREEN_WASH},{SURFACE} 60%);}}

 /* RAG pill */
 .rag {{display:inline-flex; align-items:center; gap:6px; font-family:{_MONO}; font-size:10px;
   font-weight:600; letter-spacing:.06em; text-transform:uppercase; padding:3px 9px 3px 7px; border-radius:999px;}}
 .rag .d {{width:7px; height:7px; border-radius:50%;}}
 .rag-Green {{background:{GREEN_WASH}; color:{GREEN};}} .rag-Green .d {{background:{GREEN};}}
 .rag-Amber {{background:{AMBER_WASH}; color:{AMBER};}} .rag-Amber .d {{background:{AMBER};}}
 .rag-Red   {{background:{RED_WASH}; color:{RED};}}   .rag-Red .d {{background:{RED};}}

 /* tables */
 .gv-scroll {{overflow-x:auto;}}
 table.gv {{width:100%; border-collapse:collapse; font-size:12.5px;}}
 table.gv th {{font-family:{_MONO}; font-size:9.5px; letter-spacing:.1em; text-transform:uppercase;
   color:{INK400}; font-weight:500; text-align:left; padding:8px 12px; border-bottom:1px solid {HAIR_STRONG};
   white-space:nowrap; background:{SUNKEN};}}
 table.gv td {{padding:9px 12px; border-bottom:1px solid {HAIR}; color:{INK700}; vertical-align:middle;}}
 table.gv tr:last-child td {{border-bottom:none;}}
 table.gv td.name {{color:{INK900}; font-weight:600;}}
 table.gv td.mono {{font-family:{_MONO}; color:{INK700};}}
 table.gv td.num {{font-family:{_MONO}; text-align:right;}}
 .rec-row td {{padding:2px 12px 11px; border-bottom:1px solid {HAIR}; color:{INK500}; font-size:12px;}}
 .rec-row .tag {{font-family:{_MONO}; font-size:9px; letter-spacing:.1em; text-transform:uppercase;
   color:{ACCENT_STRONG}; background:{ACCENT_WASH}; padding:2px 6px; border-radius:4px; margin-right:8px;}}

 /* mini progress bar */
 .bar {{display:inline-block; width:74px; height:6px; border-radius:4px; background:{INSET};
   vertical-align:middle; margin-right:8px; overflow:hidden;}}
 .bar > span {{display:block; height:100%; border-radius:4px; background:{ACCENT};}}
 .var-pos {{color:{RED}; font-weight:600;}} .var-zero {{color:{GREEN};}} .var-warn {{color:{AMBER}; font-weight:600;}}

 /* recommendation cards */
 .rec-card {{background:{SURFACE}; border:1px solid {HAIR}; border-radius:11px; padding:13px 15px;
   box-shadow:0 1px 2px rgba(16,21,29,.04); margin-bottom:10px;}}
 .rec-card .h {{display:flex; align-items:center; gap:10px; margin-bottom:6px;}}
 .rec-card .h .nm {{font-size:13px; font-weight:600; color:{INK900};}}
 .rec-card .bd {{font-size:12.5px; color:{INK700}; line-height:1.5;}}

 /* narrative */
 .narr {{background:{INSET}; border:1px solid {HAIR}; border-radius:11px; padding:16px 18px;
   font-size:13.5px; line-height:1.62; color:{INK700};}}
 .narr .src {{font-family:{_MONO}; font-size:9px; letter-spacing:.1em; text-transform:uppercase;
   margin-bottom:9px; display:inline-block; padding:3px 8px; border-radius:5px;}}
 .src-gemma {{background:{ACCENT_WASH}; color:{ACCENT_STRONG};}}
 .src-fallback {{background:{SUNKEN}; color:{INK500};}}

 /* validation */
 .val-card {{background:{SURFACE}; border:1px solid {HAIR}; border-radius:11px; padding:13px 15px;
   box-shadow:0 1px 2px rgba(16,21,29,.04); margin-bottom:10px;}}
 .val-card .h {{display:flex; align-items:center; justify-content:space-between; gap:10px; margin-bottom:8px;}}
 .val-card .nm {{font-size:13px; font-weight:600; color:{INK900};}}
 .val-chip {{font-family:{_MONO}; font-size:10px; letter-spacing:.06em; padding:3px 9px; border-radius:999px;}}
 .ok {{background:{GREEN_WASH}; color:{GREEN};}} .warn {{background:{AMBER_WASH}; color:{AMBER};}}
 .val-meta {{display:flex; gap:18px; flex-wrap:wrap; font-family:{_MONO}; font-size:11px; color:{INK500};}}
 .val-meta b {{color:{INK900}; font-weight:600;}}
 .val-issues {{margin:9px 0 0; padding:0 0 0 16px; color:{AMBER}; font-size:11.5px;}}

 /* Streamlit tab styling */
 .stTabs [data-baseweb="tab-list"] {{gap:3px; background:{INSET}; padding:4px; border-radius:10px;
   border:1px solid {HAIR}; margin-bottom:16px;}}
 .stTabs [data-baseweb="tab"] {{height:auto; padding:8px 15px; background:transparent; border-radius:7px;
   font-family:{_MONO}; font-size:11px; letter-spacing:.06em; text-transform:uppercase; color:{INK500};}}
 .stTabs [aria-selected="true"] {{background:{SURFACE} !important; color:{INK900} !important;
   box-shadow:0 1px 2px rgba(16,21,29,.08);}}
 .stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {{display:none;}}
</style>
"""


# --------------------------------------------------------------------------- #
# small HTML component builders
# --------------------------------------------------------------------------- #
def rag_pill(rag: str) -> str:
    return f'<span class="rag rag-{_esc(rag)}"><span class="d"></span>{_esc(rag)}</span>'


_LEVEL_COLOR = {
    "Critical": (RED, RED_WASH), "High": (AMBER, AMBER_WASH),
    "Medium": (ACCENT_STRONG, ACCENT_WASH), "Low": (INK500, SUNKEN),
}


def rag_pill_generic(level: str) -> str:
    """A colored pill for a risk *level* (Critical/High/Medium/Low)."""
    c, w = _LEVEL_COLOR.get(level, (INK500, SUNKEN))
    return (f'<span class="rag" style="background:{w};color:{c}">'
            f'<span class="d" style="background:{c}"></span>{_esc(level)}</span>')


def topbar(title: str, subtitle: str, env: str = "Simulation · Mock data") -> str:
    return (
        f'<div class="gv-top"><div>'
        f'<div class="eyebrow">AI-Driven Project Governance</div>'
        f'<h1>{_esc(title)}</h1><div class="sub">{_esc(subtitle)}</div></div>'
        f'<div class="env-pill"><span class="env-dot"></span>'
        f'<span class="lab">{_esc(env)}</span></div></div>'
    )


def stepper(active: int) -> str:
    steps = ["Upload Project Plan", "Data Validation", "AI Analysis", "Executive Dashboard"]
    cells = []
    for i, label in enumerate(steps, 1):
        cls = "done" if i < active else ("active" if i == active else "")
        mark = "✓" if i < active else str(i)
        cells.append(f'<div class="step {cls}"><span class="n">{mark}</span><span class="t">{label}</span></div>')
        if i < len(steps):
            cells.append('<div class="step-sep"></div>')
    return f'<div class="stepper">{"".join(cells)}</div>'


def kpi_row(cards: list[dict]) -> str:
    out = []
    for c in cards:
        hl = f" hl-{c['hl']}" if c.get("hl") else ""
        unit = f'<span class="u">{_esc(c["unit"])}</span>' if c.get("unit") else ""
        out.append(
            f'<div class="kpi{hl}"><div class="lab">{_esc(c["label"])}</div>'
            f'<div class="val">{_esc(c["value"])}{unit}</div>'
            f'<div class="foot">{_esc(c.get("foot", ""))}</div></div>'
        )
    return f'<div class="gv-kpis">{"".join(out)}</div>'


def _variance_cell(v: int) -> str:
    if v <= 0:
        return '<span class="var-zero">On plan</span>'
    cls = "var-pos" if v > 21 else "var-warn"
    return f'<span class="{cls}">+{v}d</span>'


def portfolio_table(projects: list[dict], recs: dict[str, str]) -> str:
    head = ("<tr><th>Project</th><th>Phase</th><th>Progress</th><th>Health</th>"
            "<th>Risk</th><th>Planned GL</th><th>Forecast GL</th><th>Variance</th><th>Owner</th></tr>")
    body = []
    for p in projects:
        pct = p["pct_complete"]
        body.append(
            f'<tr><td class="name">{_esc(p["name"])}</td>'
            f'<td>{_esc(p["phase"])}</td>'
            f'<td><span class="bar"><span style="width:{pct:.0f}%"></span></span>'
            f'<span class="mono">{pct:.0f}%</span></td>'
            f'<td>{rag_pill(p["rag"])}</td>'
            f'<td class="num">{p["risk_score"]}</td>'
            f'<td class="mono">{_esc(p["planned_go_live"] or "—")}</td>'
            f'<td class="mono">{_esc(p["forecast_go_live"] or "—")}</td>'
            f'<td class="mono">{_variance_cell(p["schedule_variance_days"])}</td>'
            f'<td>{_esc(p["owner"] or "—")}</td></tr>'
        )
        rec = recs.get(p["name"])
        if rec:
            body.append(f'<tr class="rec-row"><td colspan="9"><span class="tag">AI</span>{_esc(rec)}</td></tr>')
    return f'<div class="gv-scroll"><table class="gv">{head}{"".join(body)}</table></div>'


def simple_table(headers: list[str], rows: list[list], aligns: list[str] | None = None) -> str:
    aligns = aligns or ["" for _ in headers]
    head = "<tr>" + "".join(f"<th>{_esc(h)}</th>" for h in headers) + "</tr>"
    body = []
    for r in rows:
        cells = []
        for val, al in zip(r, aligns):
            cls = {"num": "num", "mono": "mono", "name": "name"}.get(al, "")
            raw = al == "raw"  # pass pre-rendered HTML through
            cells.append(f'<td class="{cls}">{val if raw else _esc(val)}</td>')
        body.append("<tr>" + "".join(cells) + "</tr>")
    return f'<div class="gv-scroll"><table class="gv">{head}{"".join(body)}</table></div>'


def section(title: str, meta: str = "") -> str:
    return f'<div class="sec-head"><h3>{_esc(title)}</h3><span class="meta">{_esc(meta)}</span></div>'


def narrative_block(text: str, source: str) -> str:
    lab = "Gemma 4 · live" if source == "gemma" else "Local synthesis"
    cls = "src-gemma" if source == "gemma" else "src-fallback"
    return (f'<div class="narr"><span class="src {cls}">{lab}</span>'
            f'<div>{_esc(text)}</div></div>')


def rec_card(name: str, rag: str, text: str) -> str:
    return (f'<div class="rec-card"><div class="h">{rag_pill(rag)}'
            f'<span class="nm">{_esc(name)}</span></div>'
            f'<div class="bd">{_esc(text)}</div></div>')


def validation_card(name: str, v: dict) -> str:
    chip = ('<span class="val-chip ok">Validated</span>' if v["ok"]
            else '<span class="val-chip warn">Review</span>')
    meta = (f'<div class="val-meta"><span><b>{v["task_count"]}</b> tasks</span>'
            f'<span><b>{v["phase_count"]}</b> phases</span>'
            f'<span><b>{len(v["columns_detected"])}</b> fields mapped</span>'
            f'<span>coverage <b>{v["coverage_pct"]}%</b></span></div>')
    issues = ""
    if v["issues"]:
        lis = "".join(f"<li>{_esc(i)}</li>" for i in v["issues"])
        issues = f'<ul class="val-issues">{lis}</ul>'
    return (f'<div class="val-card"><div class="h"><span class="nm">{_esc(name)}</span>{chip}</div>'
            f'{meta}{issues}</div>')


# --------------------------------------------------------------------------- #
# Plotly charts
# --------------------------------------------------------------------------- #
def _style(fig: go.Figure, height: int = 260, legend: bool = False) -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=_SANS, size=12, color=INK700),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(size=11)),
        hoverlabel=dict(bgcolor=SURFACE, font_size=12, font_family=_SANS, bordercolor=HAIR),
    )
    fig.update_xaxes(gridcolor=HAIR, zerolinecolor=HAIR, linecolor=HAIR, tickfont=dict(color=INK500))
    fig.update_yaxes(gridcolor=HAIR, zerolinecolor=HAIR, linecolor=HAIR, tickfont=dict(color=INK500))
    return fig


def rag_donut(rag: dict) -> go.Figure:
    labels = ["Green", "Amber", "Red"]
    vals = [rag.get(k, 0) for k in labels]
    fig = go.Figure(go.Pie(
        labels=labels, values=vals, hole=0.66,
        marker=dict(colors=[GREEN, AMBER, RED], line=dict(color=SURFACE, width=2)),
        sort=False, direction="clockwise", textinfo="value",
        textfont=dict(family=_MONO, size=13, color="#fff"),
        hovertemplate="%{label}: %{value}<extra></extra>",
    ))
    return _style(fig, height=210, legend=True)


def risk_bar(projects: list[dict]) -> go.Figure:
    ps = sorted(projects, key=lambda p: p["risk_score"])
    colors = [RAG_COLOR[p["rag"]][0] for p in ps]
    fig = go.Figure(go.Bar(
        x=[p["risk_score"] for p in ps], y=[p["name"] for p in ps],
        orientation="h", marker=dict(color=colors),
        text=[p["risk_score"] for p in ps], textposition="outside",
        textfont=dict(family=_MONO, size=11, color=INK700),
        hovertemplate="%{y}: risk %{x}<extra></extra>",
    ))
    fig.add_vline(x=60, line=dict(color=RED, width=1, dash="dot"))
    fig.update_xaxes(range=[0, 100], title=None)
    return _style(fig, height=230)


def go_live_timeline(go_live: list[dict]) -> go.Figure:
    """Planned vs forecast go-live as paired dumbbell markers per project."""
    import pandas as pd
    rows = [g for g in go_live if g["planned"] or g["forecast"]]
    fig = go.Figure()
    names = [g["project"] for g in rows]
    for g in rows:
        pl = pd.to_datetime(g["planned"]) if g["planned"] else None
        fc = pd.to_datetime(g["forecast"]) if g["forecast"] else None
        if pl is not None and fc is not None:
            fig.add_trace(go.Scatter(
                x=[pl, fc], y=[g["project"], g["project"]], mode="lines",
                line=dict(color=HAIR_STRONG, width=3), hoverinfo="skip", showlegend=False))
    plns = [(pd.to_datetime(g["planned"]) if g["planned"] else None) for g in rows]
    fcs = [(pd.to_datetime(g["forecast"]) if g["forecast"] else None) for g in rows]
    fig.add_trace(go.Scatter(
        x=plns, y=names, mode="markers", name="Planned",
        marker=dict(color=ACCENT, size=11, symbol="circle"),
        hovertemplate="%{y} planned %{x|%b %d, %Y}<extra></extra>"))
    fig.add_trace(go.Scatter(
        x=fcs, y=names, mode="markers", name="Forecast",
        marker=dict(color=[RAG_COLOR[g["rag"]][0] for g in rows], size=13, symbol="diamond",
                    line=dict(color=SURFACE, width=1)),
        hovertemplate="%{y} forecast %{x|%b %d, %Y}<extra></extra>"))
    return _style(fig, height=max(200, 60 + 46 * len(rows)), legend=True)


def load_bar(items: list[dict], key: str, title: str) -> go.Figure:
    items = items[:10]
    fig = go.Figure(go.Bar(
        x=[i["open"] for i in items], y=[i[key] for i in items], orientation="h",
        marker=dict(color=ACCENT), name="Open",
        hovertemplate="%{y}: %{x} open<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=[i["critical_path"] for i in items], y=[i[key] for i in items], orientation="h",
        marker=dict(color=AMBER), name="Critical-path",
        hovertemplate="%{y}: %{x} critical-path<extra></extra>",
    ))
    fig.update_layout(barmode="overlay")
    fig.update_yaxes(autorange="reversed")
    return _style(fig, height=max(200, 50 + 34 * len(items)), legend=True)


def phase_progress(project: dict) -> go.Figure:
    phs = project["phases"]
    fig = go.Figure(go.Bar(
        x=[p["pct_complete"] for p in phs], y=[p["phase"] for p in phs], orientation="h",
        marker=dict(color=RAG_COLOR[project["rag"]][0]),
        text=[f'{p["pct_complete"]:.0f}%' for p in phs], textposition="outside",
        textfont=dict(family=_MONO, size=10, color=INK500),
        hovertemplate="%{y}: %{x:.0f}%<extra></extra>",
    ))
    fig.update_xaxes(range=[0, 108])
    fig.update_yaxes(autorange="reversed")
    return _style(fig, height=230)
