"""AI-Driven Project Governance Platform — React-embedded executive dashboard.

Architecture (matches the Meridian/ParkerJones pattern):

  * Streamlit is the host + data plane: it gates access, takes the project-plan
    upload, runs the cached Pandas governance engine (governance/), and injects
    the computed portfolio as JSON.
  * The dashboard itself is a self-contained React app (ui/dashboard.html)
    mounted full-bleed via components.html — Portfolio, Risks, Go-Live,
    Resources, Milestones, AI Insights, Reports.

Runs on simulated mock data; no production systems are connected.
Run:  streamlit run app.py      (the legacy native/console apps are console_app.py)
"""
from __future__ import annotations

import glob
import os
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from governance import build_portfolio, parse_plan
from governance.ai import executive_narrative, portfolio_recommendations
from ui.bundle import render_dashboard_html

SAMPLE_GLOB = str(Path(__file__).resolve().parent / "data" / "samples" / "*.xlsx")

st.set_page_config(
    page_title="AI-Driven Project Governance Platform",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)


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
        "<style>.block-container{max-width:430px !important;padding-top:9vh !important;}"
        "#MainMenu,header,footer{display:none !important;}</style>"
        '<div style="font-family:ui-monospace,monospace;font-size:10px;letter-spacing:.14em;'
        'text-transform:uppercase;color:#8A94A2">AI-Driven Project Governance</div>'
        '<h1 style="font-size:26px;font-weight:600;letter-spacing:-.015em;margin:6px 0 4px;color:#0F141A">'
        "Governance Platform</h1>"
        '<p style="font-size:13px;color:#5E6A79;margin:0 0 20px">'
        "Executive decision-support console. Enter the access key to continue.</p>",
        unsafe_allow_html=True,
    )
    with st.form("login"):
        pw = st.text_input("Access key", type="password", placeholder="Access key", label_visibility="collapsed")
        ok = st.form_submit_button("Enter console", use_container_width=True)
    if ok:
        if pw == APP_PASSWORD:
            st.session_state.authed = True
            st.rerun()
        else:
            st.error("Incorrect access key.")
    st.markdown(
        '<p style="margin-top:18px;font-size:11.5px;color:#8A94A2;line-height:1.5">'
        "Simulation sandbox · mock data only. Deliverables are Work Made for Hire.</p>",
        unsafe_allow_html=True,
    )
    return False


# --------------------------------------------------------------------------- #
# ingestion + payload
# --------------------------------------------------------------------------- #
def load_results(uploads) -> list[dict]:
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


def build_payload(plans: list, results: list[dict]) -> dict:
    if not plans:
        return {"hasData": False}
    port = build_portfolio(plans)
    recs = {r["project"]: r["text"] for r in portfolio_recommendations(port)}
    for p in port["projects"]:
        p["recommendation"] = recs.get(p["name"], "")
    validation = []
    for r in results:
        if r.get("plan"):
            v = r["validation"]
            validation.append({"name": r["name"], "ok": v["ok"], "task_count": v["task_count"],
                               "phase_count": v["phase_count"], "coverage_pct": v["coverage_pct"],
                               "issues": v["issues"]})
        else:
            validation.append({"name": r["name"], "ok": False, "error": r.get("error", "")})
    return {
        "hasData": True,
        "meta": {"generated": port.get("generated")},
        "summary": port["summary"],
        "projects": port["projects"],
        "risk_register": port["risk_register"],
        "go_live": port["go_live"],
        "resources": port["resources"],
        "milestones": port["milestones"],
        "validation": validation,
        # instant local synthesis is shown by default; the React app can regenerate
        # live with Gemma 4 client-side on demand.
        "narrative": executive_narrative(port, ""),
    }


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main() -> None:
    if not require_login():
        return

    # Full-bleed host: strip Streamlit chrome, pin the embed to the viewport.
    st.markdown(
        """<style>
          #MainMenu, header[data-testid="stHeader"], footer {display:none !important;}
          [data-testid="stStatusWidget"], [data-testid="stDecoration"] {display:none !important;}
          html, body {overflow:hidden !important;}
          .block-container, [data-testid="stMainBlockContainer"] {padding:0 !important; max-width:100% !important;}
          [data-testid="stVerticalBlock"] {gap:0 !important;}
          iframe {height:100vh !important; width:100% !important; border:0; display:block;}
          [data-testid="stSidebar"] {border-right:1px solid #E3E7ED;}
        </style>""",
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.markdown(
            '<div style="font-family:ui-monospace,monospace;font-size:10px;letter-spacing:.12em;'
            'text-transform:uppercase;color:#8A94A2;margin-bottom:2px">Data source</div>'
            '<div style="font-size:15px;font-weight:600;margin-bottom:12px">Project plans</div>',
            unsafe_allow_html=True,
        )
        uploads = st.file_uploader("Upload project plan(s)", type=["xlsx"],
                                   accept_multiple_files=True, label_visibility="collapsed")
        if st.button("Load sample portfolio", use_container_width=True):
            st.session_state.source = "sample"
        if uploads:
            st.session_state.source = "upload"

    results = load_results(uploads)
    plans = [r["plan"] for r in results if r.get("plan")]
    payload = build_payload(plans, results)

    with st.sidebar:
        if results:
            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
            st.caption("Ingested · normalized to governance schema")
            for r in results:
                if r.get("plan"):
                    v = r["validation"]
                    dot = "#1A8A5A" if v["ok"] else "#B07A12"
                    tag = "Validated" if v["ok"] else "Review"
                    st.markdown(
                        f'<div style="display:flex;align-items:center;gap:7px;margin-top:6px">'
                        f'<span style="width:7px;height:7px;border-radius:50%;background:{dot}"></span>'
                        f'<b style="font-size:12.5px">{r["name"]}</b>'
                        f'<span style="font-family:ui-monospace,monospace;font-size:9px;color:{dot}">{tag}</span></div>'
                        f'<div style="font-family:ui-monospace,monospace;font-size:11px;color:#5E6A79;margin-left:14px">'
                        f'{v["task_count"]} tasks · {v["phase_count"]} phases · {v["coverage_pct"]}% coverage</div>',
                        unsafe_allow_html=True,
                    )
                    for issue in v["issues"]:
                        st.markdown(
                            f'<div style="font-size:11px;color:#B07A12;margin:2px 0 0 14px">{issue}</div>',
                            unsafe_allow_html=True,
                        )
                else:
                    st.markdown(f"**{r['name']}** — could not parse")
                    st.caption(r.get("error", ""))
        else:
            st.caption("Upload a plan or load the sample portfolio to begin.")

    components.html(render_dashboard_html(payload, GEMINI_KEY), height=900, scrolling=False)


main()
