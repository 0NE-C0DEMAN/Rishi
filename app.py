"""AI-Driven Project Governance Platform — executive dashboard.

Implements the client's workflow end to end:

    Upload Project Plan -> Data Validation -> AI Analysis -> Executive Dashboard
      -> Portfolio · Risks · Go-Live · Resources · Milestones · AI Insights · Reports

A project-plan workbook (the client's WBS template) is parsed and normalized by
the governance engine (governance/), which derives portfolio intelligence —
phase, % complete, RAG health, risk score, planned/forecast go-live, schedule
variance, owner — plus AI-generated recommendations. Runs on simulated mock
data; no production systems are connected.

Run:  streamlit run app.py       (the legacy telemetry console is console_app.py)
"""
from __future__ import annotations

import glob
import io
import os
from pathlib import Path

import pandas as pd
import streamlit as st

import ui.exec_ui as U
from governance import build_portfolio, parse_plan
from governance.ai import executive_narrative, portfolio_recommendations

SAMPLE_GLOB = str(Path(__file__).resolve().parent / "data" / "samples" / "*.xlsx")

st.set_page_config(
    page_title="AI-Driven Project Governance Platform",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="collapsed",
)
st.markdown(U.CSS, unsafe_allow_html=True)


def _secret(key: str, env: str, default: str = "") -> str:
    try:
        val = st.secrets[key]
        if val:
            return val
    except Exception:
        pass
    return os.environ.get(env, default)


APP_PASSWORD = _secret("app_password", "APP_PASSWORD", "demo123")
GEMINI_KEY = _secret("gemini_api_key", "GEMINI_API_KEY")


# --------------------------------------------------------------------------- #
# login gate
# --------------------------------------------------------------------------- #
def require_login() -> bool:
    if st.session_state.get("authed"):
        return True
    st.markdown(
        "<style>.block-container{max-width:430px !important;padding-top:9vh !important;}</style>"
        '<div class="eyebrow">AI-Driven Project Governance</div>'
        f'<h1 style="font-size:26px;font-weight:600;letter-spacing:-.015em;margin:6px 0 4px;'
        f'color:{U.INK900}">Governance Platform</h1>'
        f'<p style="font-size:13px;color:{U.INK500};margin:0 0 20px">'
        "Executive decision-support console. Enter the access key to continue.</p>",
        unsafe_allow_html=True,
    )
    with st.form("login", clear_on_submit=False):
        pw = st.text_input("Access key", type="password", placeholder="Access key",
                           label_visibility="collapsed")
        ok = st.form_submit_button("Enter console", use_container_width=True)
    if ok:
        if pw == APP_PASSWORD:
            st.session_state.authed = True
            st.rerun()
        else:
            st.error("Incorrect access key.")
    st.markdown(
        f'<p style="margin-top:18px;font-size:11.5px;color:{U.INK400};line-height:1.5">'
        f'Simulation sandbox · mock data only. Deliverables are Work Made for Hire.</p>',
        unsafe_allow_html=True,
    )
    return False


# --------------------------------------------------------------------------- #
# ingestion
# --------------------------------------------------------------------------- #
def load_results(uploads) -> list[dict]:
    """Parse the active data source into per-file result records."""
    results: list[dict] = []
    if uploads:
        for f in uploads:
            try:
                plan = parse_plan(f)
                results.append({"name": plan.name, "plan": plan, "validation": plan.validation})
            except Exception as exc:
                results.append({"name": getattr(f, "name", "file"), "plan": None, "error": str(exc)})
    elif st.session_state.get("source") == "sample":
        for fp in sorted(glob.glob(SAMPLE_GLOB)):
            try:
                plan = parse_plan(fp)
                results.append({"name": plan.name, "plan": plan, "validation": plan.validation})
            except Exception as exc:
                results.append({"name": Path(fp).stem, "plan": None, "error": str(exc)})
    return results


# --------------------------------------------------------------------------- #
# dashboard tabs
# --------------------------------------------------------------------------- #
def tab_portfolio(port: dict, recs: dict) -> None:
    s = port["summary"]
    st.markdown(U.kpi_row([
        {"label": "Programmes", "value": s["project_count"], "foot": "in portfolio"},
        {"label": "Portfolio health", "value": s["portfolio_health"], "hl": s["portfolio_health"].lower(),
         "foot": f'{s["rag"]["Red"]}R · {s["rag"]["Amber"]}A · {s["rag"]["Green"]}G'},
        {"label": "Avg risk score", "value": s["avg_risk"], "unit": "/100", "foot": "governance engine"},
        {"label": "Avg complete", "value": f'{s["avg_complete"]:.0f}', "unit": "%", "foot": "weighted"},
        {"label": "Slipping", "value": f'{s["slipping"]}/{s["project_count"]}', "foot": "forecast late",
         "hl": "amber" if s["slipping"] else None},
        {"label": "Critical risks", "value": s["critical_risks"], "foot": "open", "unit": "",
         "hl": "red" if s["critical_risks"] else None},
    ]), unsafe_allow_html=True)

    left, right = st.columns([2, 1], gap="medium")
    with left:
        st.markdown(U.section("Portfolio", f'next go-live {s["next_go_live"] or "—"}'), unsafe_allow_html=True)
        st.markdown(U.portfolio_table(port["projects"], recs), unsafe_allow_html=True)
    with right:
        st.markdown(U.section("Health mix"), unsafe_allow_html=True)
        st.plotly_chart(U.rag_donut(s["rag"]), use_container_width=True, config={"displayModeBar": False})
        st.markdown(U.section("Risk by programme"), unsafe_allow_html=True)
        st.plotly_chart(U.risk_bar(port["projects"]), use_container_width=True, config={"displayModeBar": False})


def tab_risks(port: dict) -> None:
    reg = port["risk_register"]
    openc = sum(1 for r in reg if r["open"])
    crit = sum(1 for r in reg if r["risk_level"] == "Critical")
    high = sum(1 for r in reg if r["risk_level"] == "High")
    st.markdown(U.kpi_row([
        {"label": "Risk items", "value": len(reg), "foot": "medium and above"},
        {"label": "Open", "value": openc, "foot": "unresolved", "hl": "amber" if openc else None},
        {"label": "Critical", "value": crit, "foot": "highest severity", "hl": "red" if crit else None},
        {"label": "High", "value": high, "foot": "elevated"},
    ]), unsafe_allow_html=True)

    left, right = st.columns([2, 1], gap="medium")
    with left:
        st.markdown(U.section("Risk register", "ranked by exposure"), unsafe_allow_html=True)
        rows = [[
            r["project"], r["phase"], r["activity"],
            U.rag_pill_generic(r["risk_level"]), r["owner"] or "—",
            r["status"], r["planned_finish"] or "—",
        ] for r in reg[:40]]
        st.markdown(U.simple_table(
            ["Project", "Phase", "Risk", "Level", "Owner", "Status", "Planned finish"],
            rows, aligns=["name", "", "", "raw", "", "", "mono"]), unsafe_allow_html=True)
        if len(reg) > 40:
            st.caption(f"Showing top 40 of {len(reg)} risk items by exposure.")
    with right:
        st.markdown(U.section("Exposure by programme"), unsafe_allow_html=True)
        by_proj: dict[str, float] = {}
        for r in reg:
            by_proj[r["project"]] = by_proj.get(r["project"], 0) + r["exposure"]
        proj_rows = [{"name": k, "risk_score": round(v * 10), "rag": _rag_for(port, k)}
                     for k, v in by_proj.items()]
        st.plotly_chart(U.risk_bar(proj_rows), use_container_width=True, config={"displayModeBar": False})


def tab_go_live(port: dict) -> None:
    gl = port["go_live"]
    st.markdown(U.section("Go-live outlook", "planned vs forecast"), unsafe_allow_html=True)
    st.plotly_chart(U.go_live_timeline(gl), use_container_width=True, config={"displayModeBar": False})
    rows = [[
        g["project"], g["planned"] or "—", g["forecast"] or "—",
        U._variance_cell(g["variance_days"]), U.rag_pill(g["rag"]),
    ] for g in gl]
    st.markdown(U.simple_table(
        ["Project", "Planned go-live", "Forecast go-live", "Variance", "Health"],
        rows, aligns=["name", "mono", "mono", "raw", "raw"]), unsafe_allow_html=True)


def tab_resources(port: dict) -> None:
    res = port["resources"]
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        st.markdown(U.section("Load by team", "open vs critical-path tasks"), unsafe_allow_html=True)
        st.plotly_chart(U.load_bar(res["by_team"], "team", "team"),
                        use_container_width=True, config={"displayModeBar": False})
    with c2:
        st.markdown(U.section("Load by owner", "top contributors"), unsafe_allow_html=True)
        st.plotly_chart(U.load_bar(res["by_owner"], "owner", "owner"),
                        use_container_width=True, config={"displayModeBar": False})
    st.markdown(U.section("Owner allocation"), unsafe_allow_html=True)
    rows = [[o["owner"], o["tasks"], o["open"], o["active"], o["critical_path"]]
            for o in res["by_owner"][:15]]
    st.markdown(U.simple_table(
        ["Owner", "Tasks", "Open", "Active", "Critical-path"], rows,
        aligns=["name", "num", "num", "num", "num"]), unsafe_allow_html=True)


def tab_milestones(port: dict) -> None:
    ms = port["milestones"]
    names = [p["name"] for p in port["projects"]]
    overdue = sum(1 for m in ms if m["overdue"])
    st.markdown(U.kpi_row([
        {"label": "Milestones", "value": len(ms), "foot": "gates + critical path"},
        {"label": "Complete", "value": sum(1 for m in ms if m["done"]), "foot": "delivered", "hl": "green"},
        {"label": "Overdue", "value": overdue, "foot": "past planned finish", "hl": "red" if overdue else None},
        {"label": "Programmes", "value": len(names), "foot": "tracked"},
    ]), unsafe_allow_html=True)
    left, right = st.columns([2, 1], gap="medium")
    with left:
        st.markdown(U.section("Milestone tracker", "earliest first"), unsafe_allow_html=True)
        rows = []
        for m in ms[:40]:
            status = ("Complete" if m["done"] else ("Overdue" if m["overdue"] else m["status"]))
            rows.append([m["project"], m["phase"], m["milestone"],
                         m["planned_finish"] or "—", status])
        st.markdown(U.simple_table(
            ["Project", "Phase", "Milestone", "Planned", "Status"],
            rows, aligns=["name", "", "", "mono", ""]), unsafe_allow_html=True)
    with right:
        st.markdown(U.section("Phase progress"), unsafe_allow_html=True)
        pick = st.selectbox("Project", names, label_visibility="collapsed")
        proj = next(p for p in port["projects"] if p["name"] == pick)
        st.plotly_chart(U.phase_progress(proj), use_container_width=True, config={"displayModeBar": False})


def tab_ai(port: dict, recs: dict) -> None:
    st.markdown(U.section("Executive narrative", "explainable AI · Gemma 4"), unsafe_allow_html=True)
    c1, c2 = st.columns([1, 3])
    with c1:
        gen = st.button("Generate with Gemma 4", use_container_width=True, type="primary",
                        disabled=not GEMINI_KEY)
    with c2:
        if GEMINI_KEY:
            st.caption("A local synthesis shows instantly. Click to regenerate live with **Gemma 4** — "
                       "the model reasons over the portfolio before answering, so it takes ~60–90s.")
        else:
            st.caption("Showing local synthesis. Configure `gemini_api_key` to enable the live Gemma 4 model.")
    if gen:
        with st.spinner("Gemma 4 is reasoning over the portfolio… (~60–90s)"):
            st.session_state.gemma_narrative = executive_narrative(port, GEMINI_KEY)
    # Live Gemma result persists once generated; otherwise show the instant synthesis.
    narr = st.session_state.get("gemma_narrative") or executive_narrative(port, "")
    st.markdown(U.narrative_block(narr["text"], narr["source"]), unsafe_allow_html=True)
    if narr.get("error"):
        st.caption(f"Live model unavailable — {narr['error']}. Showing local synthesis.")
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    st.markdown(U.section("AI recommendations", "one action per programme"), unsafe_allow_html=True)
    cols = st.columns(2, gap="medium")
    for i, p in enumerate(port["projects"]):
        with cols[i % 2]:
            st.markdown(U.rec_card(p["name"], p["rag"], recs.get(p["name"], "")), unsafe_allow_html=True)


def tab_reports(port: dict, recs: dict) -> None:
    st.markdown(U.section("Reports & exports", "normalized governance data"), unsafe_allow_html=True)
    proj_df = pd.DataFrame([{
        "Project": p["name"], "Owner": p["owner"], "Phase": p["phase"],
        "% Complete": p["pct_complete"], "Health (RAG)": p["rag"], "Risk score": p["risk_score"],
        "Planned go-live": p["planned_go_live"], "Forecast go-live": p["forecast_go_live"],
        "Schedule variance (days)": p["schedule_variance_days"],
        "AI recommendation": recs.get(p["name"], ""),
    } for p in port["projects"]])
    risk_df = pd.DataFrame(port["risk_register"])
    mile_df = pd.DataFrame(port["milestones"])

    st.dataframe(proj_df, use_container_width=True, hide_index=True)

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        proj_df.to_excel(xw, sheet_name="Portfolio", index=False)
        risk_df.to_excel(xw, sheet_name="Risk register", index=False)
        mile_df.to_excel(xw, sheet_name="Milestones", index=False)
    c1, c2, c3 = st.columns(3)
    c1.download_button("Portfolio (CSV)", proj_df.to_csv(index=False).encode(),
                       "portfolio.csv", "text/csv", use_container_width=True)
    c2.download_button("Risk register (CSV)", risk_df.to_csv(index=False).encode(),
                       "risk_register.csv", "text/csv", use_container_width=True)
    c3.download_button("Full workbook (XLSX)", buf.getvalue(),
                       "governance_report.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       use_container_width=True)


def _rag_for(port: dict, project_name: str) -> str:
    for p in port["projects"]:
        if p["name"] == project_name:
            return p["rag"]
    return "Amber"


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main() -> None:
    if not require_login():
        return

    st.markdown(U.topbar(
        "Executive Governance Dashboard",
        "Upload a project plan to generate portfolio intelligence, RAG health, and AI recommendations.",
    ), unsafe_allow_html=True)

    ctrl, act = st.columns([3, 1], gap="medium")
    with ctrl:
        uploads = st.file_uploader(
            "Upload project plan(s)", type=["xlsx"], accept_multiple_files=True,
            label_visibility="collapsed",
            help="Upload one or more project-plan workbooks in the WBS template format.",
        )
    with act:
        if st.button("Load sample portfolio", use_container_width=True):
            st.session_state.source = "sample"
    if uploads:
        st.session_state.source = "upload"

    results = load_results(uploads)
    plans = [r["plan"] for r in results if r.get("plan")]

    if not plans:
        st.markdown(U.stepper(1), unsafe_allow_html=True)
        for r in results:
            if r.get("error"):
                st.warning(f"**{r['name']}** could not be parsed — {r['error']}")
        st.info("Upload a project-plan workbook (.xlsx), or click **Load sample portfolio** "
                "to explore the dashboard with example programmes.")
        return

    st.markdown(U.stepper(4), unsafe_allow_html=True)

    any_issue = any(r.get("error") or (r.get("validation") and not r["validation"]["ok"]) for r in results)
    with st.expander(f"Data validation — {len(plans)} plan(s) ingested, normalized to the governance schema",
                     expanded=any_issue):
        for r in results:
            if r.get("plan"):
                st.markdown(U.validation_card(r["name"], r["validation"]), unsafe_allow_html=True)
            else:
                st.markdown(
                    f'<div class="val-card"><div class="h"><span class="nm">{r["name"]}</span>'
                    f'<span class="val-chip warn">Failed</span></div>'
                    f'<div class="val-meta">{r.get("error", "")}</div></div>',
                    unsafe_allow_html=True)

    port = build_portfolio(plans)
    recs = {r["project"]: r["text"] for r in portfolio_recommendations(port)}

    tabs = st.tabs(["Portfolio", "Risks", "Go-Live", "Resources", "Milestones", "AI Insights", "Reports"])
    with tabs[0]:
        tab_portfolio(port, recs)
    with tabs[1]:
        tab_risks(port)
    with tabs[2]:
        tab_go_live(port)
    with tabs[3]:
        tab_resources(port)
    with tabs[4]:
        tab_milestones(port)
    with tabs[5]:
        tab_ai(port, recs)
    with tabs[6]:
        tab_reports(port, recs)


main()
