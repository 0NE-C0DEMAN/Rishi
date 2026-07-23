"""AI-Driven Project Governance Platform — React-embedded executive dashboard.

Architecture (matches the Meridian/ParkerJones pattern):

  * Streamlit is the host + data plane: it gates access, presents the upload
    landing, runs the cached Pandas governance engine (governance/), and injects
    the computed portfolio as JSON.
  * The dashboard itself is a self-contained React app (ui/dashboard.html)
    mounted full-bleed via components.html — Portfolio, Risks, Go-Live,
    Resources, Milestones, AI Insights, Reports.

Runs on simulated mock data; no production systems are connected.
Run:  streamlit run app.py      (the legacy console app is console_app.py)
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
# ingestion
# --------------------------------------------------------------------------- #
def _parse_files(files) -> list[dict]:
    out = []
    for f in files:
        try:
            plan = parse_plan(f)
            out.append({"name": plan.name, "plan": plan, "validation": plan.validation})
        except Exception as exc:
            out.append({"name": getattr(f, "name", "file"), "plan": None, "error": str(exc)})
    return out


def _parse_samples() -> list[dict]:
    out = []
    for fp in sorted(glob.glob(SAMPLE_GLOB)):
        try:
            plan = parse_plan(fp)
            out.append({"name": plan.name, "plan": plan, "validation": plan.validation})
        except Exception as exc:
            out.append({"name": Path(fp).stem, "plan": None, "error": str(exc)})
    return out


def build_payload(plans: list, results: list[dict]) -> dict:
    port = build_portfolio(plans)
    recs = {r["project"]: r["text"] for r in portfolio_recommendations(port)}
    for p in port["projects"]:
        p["recommendation"] = recs.get(p["name"], "")
    return {
        "hasData": True,
        "meta": {"generated": port.get("generated")},
        "summary": port["summary"],
        "projects": port["projects"],
        "risk_register": port["risk_register"],
        "go_live": port["go_live"],
        "resources": port["resources"],
        "milestones": port["milestones"],
        "narrative": executive_narrative(port, ""),
    }


# --------------------------------------------------------------------------- #
# login gate
# --------------------------------------------------------------------------- #
def require_login() -> bool:
    if st.session_state.get("authed"):
        return True
    st.markdown(
        "<style>[data-testid='stSidebar']{display:none !important;}"
        ".block-container{max-width:430px !important;padding-top:9vh !important;}"
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
# upload landing (no data yet)
# --------------------------------------------------------------------------- #
_LANDING_CSS = """<style>
  #MainMenu, header, footer {display:none !important;}
  [data-testid="stSidebar"] {display:none !important;}
  .block-container {max-width:660px !important; padding-top:6vh !important;}
  .lz-eyebrow {font-family:ui-monospace,monospace; font-size:10px; letter-spacing:.14em; text-transform:uppercase; color:#8A94A2;}
  .lz-title {font-size:28px; font-weight:650; letter-spacing:-.02em; margin:8px 0 8px; color:#0E1733;}
  .lz-sub {font-size:14px; color:#5A6478; line-height:1.6; margin:0 0 24px; max-width:560px;}
  .lz-steps {display:flex; align-items:center; gap:0; flex-wrap:wrap; margin-bottom:24px;}
  .lz-step {display:inline-flex; align-items:center; gap:8px; font-size:12.5px; font-weight:600; color:#5A6478;
    padding:7px 13px; background:#FFFFFF; border:1px solid #E3E7EF; border-radius:9px; box-shadow:0 1px 2px rgba(14,23,51,.04);}
  .lz-step .n {width:19px; height:19px; border-radius:50%; background:#EFF2F8; color:#8A93A6;
    font-family:ui-monospace,monospace; font-size:11px; font-weight:600; display:grid; place-items:center;}
  .lz-step.on {border-color:#2D5BFF; box-shadow:0 0 0 3px #F2F6FF; color:#0E1733;}
  .lz-step.on .n {background:#2D5BFF; color:#fff;}
  .lz-sep {width:20px; height:1px; background:#CFD5E1; margin:0 2px;}
  [data-testid="stFileUploaderDropzone"] {min-height:134px !important; background:#FFFFFF !important;
    border:1.6px dashed #CFD5E1 !important; border-radius:14px !important; padding:26px !important; transition:all .15s;}
  [data-testid="stFileUploaderDropzone"]:hover {border-color:#2D5BFF !important; background:#F2F6FF !important;}
  .lz-or {display:flex; align-items:center; gap:12px; color:#8A93A6; font-size:10px; font-family:ui-monospace,monospace;
    letter-spacing:.12em; text-transform:uppercase; margin:16px 0;}
  .lz-or::before, .lz-or::after {content:""; flex:1; height:1px; background:#E3E7EF;}
  .lz-foot {margin-top:24px; font-size:11.5px; color:#8A94A2; line-height:1.5;}
</style>"""

_LANDING_HTML = """<div class="lz-eyebrow">AI-Driven Project Governance</div>
<h1 class="lz-title">Upload a project plan</h1>
<p class="lz-sub">Drop a project-plan workbook (.xlsx) and the governance engine validates it, scores delivery risk,
and builds your executive dashboard — health (RAG), risk score, schedule variance, and AI recommendations.</p>
<div class="lz-steps">
  <div class="lz-step on"><span class="n">1</span>Upload</div><span class="lz-sep"></span>
  <div class="lz-step"><span class="n">2</span>Validation</div><span class="lz-sep"></span>
  <div class="lz-step"><span class="n">3</span>AI Analysis</div><span class="lz-sep"></span>
  <div class="lz-step"><span class="n">4</span>Dashboard</div>
</div>"""


def render_landing() -> None:
    st.markdown(_LANDING_CSS, unsafe_allow_html=True)
    st.markdown(_LANDING_HTML, unsafe_allow_html=True)
    uploads = st.file_uploader("Upload project plan(s)", type=["xlsx"], accept_multiple_files=True,
                               key="up_landing", label_visibility="collapsed")
    st.markdown('<div class="lz-or">or</div>', unsafe_allow_html=True)
    sample = st.button("Load sample portfolio", type="primary", use_container_width=True)
    st.markdown(
        '<p class="lz-foot">No plan handy? Load a sample portfolio of four programmes. '
        "Simulation sandbox · mock data only.</p>",
        unsafe_allow_html=True,
    )
    if uploads:
        st.session_state.results = _parse_files(uploads)
        st.rerun()
    if sample:
        st.session_state.results = _parse_samples()
        st.rerun()


# --------------------------------------------------------------------------- #
# dashboard (data loaded)
# --------------------------------------------------------------------------- #
_DASH_CSS = """<style>
  #MainMenu, header[data-testid="stHeader"], footer {display:none !important;}
  [data-testid="stStatusWidget"], [data-testid="stDecoration"] {display:none !important;}
  html, body {overflow:hidden !important;}
  .block-container, [data-testid="stMainBlockContainer"] {padding:0 !important; max-width:100% !important;}
  /* Only the MAIN column is gap-collapsed so the iframe sits flush; the sidebar
     keeps its natural spacing (collapsing it there overlapped the cards). */
  [data-testid="stMain"] [data-testid="stVerticalBlock"] {gap:0 !important;}
  iframe {height:100vh !important; width:100% !important; border:0; display:block;}
  /* Force-show the sidebar — overrides any stale display:none carried over from
     the login/landing style blocks when Streamlit reuses the DOM. */
  [data-testid="stSidebar"] {display:flex !important; background:#F4F6FB !important; border-right:1px solid #E3E7ED;}
  [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {
    background:#FFFFFF !important; border:1.4px dashed #CFD5E1 !important; border-radius:10px !important; min-height:0 !important;}
  [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"]:hover {border-color:#2D5BFF !important; background:#F2F6FF !important;}
  [data-testid="stSidebar"] button {border-radius:9px !important; font-weight:600 !important;}
  .vcard {background:#FFFFFF; border:1px solid #E3E7EF; border-radius:10px; padding:10px 12px; margin-bottom:8px;
    box-shadow:0 1px 2px rgba(14,23,51,.04);}
  .vcard-top {display:flex; align-items:center; gap:7px;}
  .vcard-dot {width:7px; height:7px; border-radius:50%; flex:none;}
  .vcard-name {font-size:12.5px; font-weight:600; color:#0E1733;}
  .vcard-tag {margin-left:auto; font-family:ui-monospace,monospace; font-size:8.5px; font-weight:600;
    letter-spacing:.06em; text-transform:uppercase; padding:2px 6px; border-radius:5px;}
  .vcard-meta {font-family:ui-monospace,monospace; font-size:10.5px; color:#5A6478; margin-top:5px;}
  .vcard-issue {font-size:11px; color:#B07A12; margin-top:4px;}
  .side-eyebrow {font-family:ui-monospace,monospace; font-size:10px; letter-spacing:.12em; text-transform:uppercase; color:#8A94A2;}
  .side-title {font-size:15px; font-weight:650; margin:1px 0 2px; color:#0E1733;}
  .side-note {font-family:ui-monospace,monospace; font-size:10px; letter-spacing:.06em; text-transform:uppercase;
    color:#8A93A6; margin:14px 0 8px;}
</style>"""


def _validation_cards(results: list[dict]) -> str:
    rows = ""
    for r in results:
        if r.get("plan"):
            v = r["validation"]
            ok = v["ok"]
            color = "#16A34A" if ok else "#B07A12"
            wash = "#DCFCE7" if ok else "#FEF3C7"
            tag = "Validated" if ok else "Review"
            issues = "".join(f'<div class="vcard-issue">{i}</div>' for i in v["issues"])
            rows += (
                f'<div class="vcard"><div class="vcard-top">'
                f'<span class="vcard-dot" style="background:{color}"></span>'
                f'<span class="vcard-name">{r["name"]}</span>'
                f'<span class="vcard-tag" style="background:{wash};color:{color}">{tag}</span></div>'
                f'<div class="vcard-meta">{v["task_count"]} tasks · {v["phase_count"]} phases · {v["coverage_pct"]}% coverage</div>'
                f"{issues}</div>"
            )
        else:
            rows += (
                f'<div class="vcard"><div class="vcard-top">'
                f'<span class="vcard-dot" style="background:#DC2626"></span>'
                f'<span class="vcard-name">{r["name"]}</span>'
                f'<span class="vcard-tag" style="background:#FEE2E2;color:#DC2626">Failed</span></div>'
                f'<div class="vcard-issue">{r.get("error", "")}</div></div>'
            )
    return f'<div class="vlist">{rows}</div>'


def render_dashboard(results: list[dict]) -> None:
    st.markdown(_DASH_CSS, unsafe_allow_html=True)
    plans = [r["plan"] for r in results if r.get("plan")]

    with st.sidebar:
        st.markdown(
            '<div class="side-eyebrow">Data source</div><div class="side-title">Project plans</div>',
            unsafe_allow_html=True,
        )
        reupload = st.file_uploader("Load a different plan", type=["xlsx"], accept_multiple_files=True,
                                    key="up_side", label_visibility="collapsed")
        if st.button("Start over", use_container_width=True):
            for k in ("results", "up_side", "up_landing"):
                st.session_state.pop(k, None)
            st.rerun()
        st.markdown('<div class="side-note">Ingested · normalized to governance schema</div>', unsafe_allow_html=True)
        st.markdown(_validation_cards(results), unsafe_allow_html=True)

    if reupload:
        st.session_state.results = _parse_files(reupload)
        st.rerun()

    if not plans:
        st.warning("None of the uploaded files could be parsed as a project plan. Use **Start over** to try again.")
        return

    payload = build_payload(plans, results)
    components.html(render_dashboard_html(payload, GEMINI_KEY), height=900, scrolling=False)


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main() -> None:
    if not require_login():
        return
    results = st.session_state.get("results")
    if results:
        render_dashboard(results)
    else:
        render_landing()


main()
