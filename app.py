"""AI-Driven Project Governance Platform — React-embedded executive dashboard.

Architecture:

  * Streamlit is the host and data plane only. It runs the Pandas governance
    engine (governance/), injects the computed portfolio as JSON, and exposes
    three off-screen widgets (a file input and two buttons) that the embedded
    app drives so ingestion can live inside the dashboard.
  * The dashboard is a self-contained React app (ui/dashboard.html, compiled
    from ui/dashboard.src.html) mounted full-bleed via components.html:
    Portfolio, Risks, Go-Live, Resources, Milestones, AI Insights, Reports and
    Data. It owns the only left rail; Streamlit's sidebar is hidden.

The console opens directly on the dashboard with the sample portfolio loaded.
Set `require_login = true` in secrets to put the access gate in front of it
before deploying publicly.

Runs on simulated mock data; no production systems are connected.
Run:  streamlit run app.py      (the legacy telemetry console is console_app.py)
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
    initial_sidebar_state="collapsed",
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


def _flag(key: str, env: str, default: bool = False) -> bool:
    raw = _secret(key, env, "")
    if raw == "":
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


# Access gate is off by default so the console opens straight onto the
# dashboard. Turn it on (secrets: require_login = true) before deploying
# publicly, e.g. on Streamlit Community Cloud.
REQUIRE_LOGIN = _flag("require_login", "REQUIRE_LOGIN", False)

# --------------------------------------------------------------------------- #
# Design system for the Streamlit-hosted screens (login + upload landing +
# sidebar). Same tokens as the embedded React dashboard, so the whole app reads
# as one system. Presentation only.
# --------------------------------------------------------------------------- #
_FONTS = (
    '<link href="https://fonts.googleapis.com/css2?'
    "family=Outfit:wght@400;450;500;600;700;800&"
    'family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">'
)

_HOST_TOKENS = """<style>
  :root{
    --bg:#FFFFFF; --sidebar-bg:#FAFBFC; --surface:#FFFFFF; --surface-2:#F3F4F7;
    --border:#E7E9EE; --hover:#F5F6F8;
    --card-shadow:0 1px 2px rgba(17,24,39,.04), 0 4px 10px -3px rgba(17,24,39,.06);
    --text:#111827; --text-2:#4B5563; --text-3:#9CA3AF;
    --accent:#4F46E5; --accent-surface:rgba(79,70,229,.06); --accent-border:rgba(79,70,229,.2);
    --pos:#059669; --warn:#D97706; --neg:#DC2626;
    --font:'Outfit',-apple-system,sans-serif; --mono:'JetBrains Mono',monospace;
  }
  html, body, [class*="css"], button, input, select, textarea {font-family:var(--font) !important;}
  .stApp {background:var(--bg);}
  h1,h2,h3 {letter-spacing:-0.015em;}
  /* Buttons — 8px radius, tactile press, one primary per screen */
  .stButton > button, .stFormSubmitButton > button, .stDownloadButton > button {
    border-radius:8px !important; font-weight:600 !important; font-size:12.5px !important;
    border:1px solid var(--border) !important; transition:background .13s, border-color .13s, transform .1s cubic-bezier(.22,1,.36,1) !important;
  }
  .stButton > button:hover, .stFormSubmitButton > button:hover {background:var(--hover) !important; border-color:var(--text-3) !important;}
  .stButton > button:active, .stFormSubmitButton > button:active {transform:scale(0.97);}
  .stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {
    background:var(--accent) !important; border-color:var(--accent) !important; color:#fff !important;
  }
  .stButton > button[kind="primary"]:hover, .stFormSubmitButton > button[kind="primary"]:hover {background:#4338CA !important;}
  /* Inputs — must READ as editable: white field, real 1px border, accent focus
     ring. Streamlit's default is a borderless grey block that looks disabled. */
  [data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="select"] > div {
    background:var(--surface) !important;
    border:1px solid var(--border) !important;
    border-radius:8px !important;
    transition:border-color .13s, box-shadow .13s !important;
  }
  [data-baseweb="input"]:hover, [data-baseweb="select"] > div:hover {border-color:#D1D5DB !important;}
  [data-baseweb="input"]:focus-within, [data-baseweb="select"] > div:focus-within {
    border-color:var(--accent) !important; box-shadow:0 0 0 3px var(--accent-surface) !important;
  }
  .stTextInput input, [data-baseweb="input"] input {
    background:transparent !important; font-size:13px !important; color:var(--text) !important;
    padding-top:9px !important; padding-bottom:9px !important;
  }
  .stTextInput input::placeholder {color:var(--text-3) !important;}
  /* Field label above the input */
  .stTextInput label, [data-testid="stWidgetLabel"] label {
    font-size:11.5px !important; font-weight:600 !important; color:var(--text-2) !important;
  }
  ::-webkit-scrollbar {width:8px; height:8px;}
  ::-webkit-scrollbar-track {background:transparent;}
  ::-webkit-scrollbar-thumb {background:#C4C9D2; border-radius:4px;}
  ::-webkit-scrollbar-thumb:hover {background:var(--text-3);}
  ::selection {background:var(--accent-surface); color:var(--accent);}
  @media (prefers-reduced-motion: reduce) {
    * {animation-duration:.01ms !important; transition-duration:.12s !important;}
    .stButton > button:active {transform:none;}
  }
</style>"""


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
        # Ingestion status, surfaced in the dashboard's own sidebar so the app
        # presents a single left rail.
        "validation": [
            {
                "name": r["name"],
                "ok": bool(r.get("plan")) and r["validation"]["ok"],
                "tasks": r["validation"]["task_count"] if r.get("plan") else 0,
                "phases": r["validation"]["phase_count"] if r.get("plan") else 0,
                "coverage": r["validation"]["coverage_pct"] if r.get("plan") else 0,
                "failed": not r.get("plan"),
            }
            for r in results
        ],
    }


# --------------------------------------------------------------------------- #
# login gate
# --------------------------------------------------------------------------- #
def require_login() -> bool:
    if st.session_state.get("authed"):
        return True
    st.markdown(
        _FONTS + _HOST_TOKENS
        + "<style>[data-testid='stSidebar']{display:none !important;}"
        ".block-container{max-width:430px !important;padding-top:9vh !important;}"
        "#MainMenu,header,footer{display:none !important;}</style>"
        '<div style="font-size:10.5px;font-weight:700;letter-spacing:.05em;'
        'text-transform:uppercase;color:#4F46E5">AI-driven project governance</div>'
        '<h1 style="font-size:24px;font-weight:800;letter-spacing:-0.02em;margin:8px 0 6px;color:#111827">'
        "Governance Platform</h1>"
        '<p style="font-size:13px;color:#4B5563;margin:0 0 24px;line-height:1.6">'
        "Executive decision-support console. Enter the access key to continue.</p>",
        unsafe_allow_html=True,
    )
    with st.form("login"):
        pw = st.text_input("Access key", type="password", placeholder="Enter your access key")
        ok = st.form_submit_button("Enter console", use_container_width=True, type="primary")
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
# dashboard (data loaded)
# --------------------------------------------------------------------------- #
_DASH_CSS = _FONTS + _HOST_TOKENS + """<style>
  #MainMenu, header[data-testid="stHeader"], footer {display:none !important;}
  [data-testid="stStatusWidget"], [data-testid="stDecoration"] {display:none !important;}
  /* Pin the whole host chain to the viewport. components.html() reserves a
     fixed-height wrapper, so without this the embed is capped at that height
     and the leftover space renders as dead white below the app. The hidden
     bridge widgets are position:absolute, so these heights cannot stack. */
  html, body {overflow:hidden !important; height:100% !important;}
  .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
    height:100vh !important; max-height:100vh !important; overflow:hidden !important;
  }
  .block-container, [data-testid="stMainBlockContainer"] {
    padding:0 !important; max-width:100% !important; height:100vh !important; overflow:hidden !important;
  }
  [data-testid="stMain"] [data-testid="stVerticalBlock"] {gap:0 !important; height:100vh !important;}
  [data-testid="stElementContainer"]:has(iframe),
  [data-testid="stCustomComponentV1"] {height:100vh !important;}
  iframe {height:100vh !important; width:100% !important; border:0; display:block;}
  /* Force-show the sidebar — overrides any stale display:none carried over from
     the login/landing style blocks when Streamlit reuses the DOM. */
  /* The dashboard owns the only left rail — Streamlit's sidebar is unused. */
  [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {display:none !important;}
  /* Host bridge widgets: present in the DOM (so the embedded app can drive
     them) but never visible. Programmatic .click()/change still works. */
  .st-key-host_upload, .st-key-host_sample, .st-key-host_clear {
    position:absolute !important; width:1px !important; height:1px !important;
    overflow:hidden !important; opacity:0 !important; pointer-events:none !important;
    top:0 !important; left:0 !important; margin:0 !important; padding:0 !important;
  }
  [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {
    background:var(--surface) !important; border:1.4px dashed #D1D5DB !important; border-radius:10px !important; min-height:0 !important;}
  [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"]:hover {border-color:var(--accent) !important; background:var(--accent-surface) !important;}
  .vcard {background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:10px 12px; margin-bottom:8px;
    box-shadow:var(--card-shadow);}
  .vcard-top {display:flex; align-items:center; gap:7px;}
  .vcard-dot {width:7px; height:7px; border-radius:50%; flex:none;}
  .vcard-name {font-size:12.5px; font-weight:600; color:var(--text);}
  .vcard-tag {margin-left:auto; font-size:9px; font-weight:700;
    letter-spacing:.05em; text-transform:uppercase; padding:2px 7px; border-radius:7px;}
  .vcard-meta {font-family:var(--mono); font-size:10.5px; color:var(--text-2); margin-top:5px;}
  .vcard-issue {font-size:11px; color:var(--warn); margin-top:4px;}
  .side-eyebrow {font-size:10.5px; font-weight:700; letter-spacing:.05em; text-transform:uppercase; color:var(--accent);}
  .side-title {font-size:15px; font-weight:700; letter-spacing:-0.01em; margin:2px 0 2px; color:var(--text);}
  .side-note {font-size:10px; font-weight:700; letter-spacing:.05em; text-transform:uppercase;
    color:var(--text-3); margin:14px 0 8px;}
</style>"""


def render_dashboard(results: list[dict]) -> None:
    """Render the console.

    The dashboard's own Data page owns the ingestion UI, so the host only needs
    to expose the widgets that must live in Python (a file input and two action
    buttons). They are rendered off-screen and driven from the embedded app —
    that keeps a single left rail instead of a second Streamlit sidebar.
    """
    st.markdown(_DASH_CSS, unsafe_allow_html=True)

    # --- host bridge: visually hidden, driven from the embedded app ---------
    uploads = st.file_uploader(
        "Upload project plan(s)", type=["xlsx"], accept_multiple_files=True,
        key="host_upload", label_visibility="collapsed",
    )
    load_sample = st.button("Load sample", key="host_sample")
    clear_all = st.button("Clear", key="host_clear")

    if uploads:
        st.session_state.results = _parse_files(uploads)
        st.rerun()
    if load_sample:
        st.session_state.pop("host_upload", None)
        st.session_state.results = _parse_samples()
        st.rerun()
    if clear_all:
        st.session_state.pop("host_upload", None)
        st.session_state.results = []
        st.rerun()

    plans = [r["plan"] for r in results if r.get("plan")]
    payload = build_payload(plans, results) if plans else {"hasData": False, "validation": [
        {"name": r["name"], "ok": False, "failed": True, "error": r.get("error", ""), "tasks": 0, "phases": 0, "coverage": 0}
        for r in results
    ]}
    components.html(render_dashboard_html(payload, GEMINI_KEY), height=900, scrolling=False)


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main() -> None:
    # The access gate is opt-in: set `require_login = true` in secrets before
    # exposing the app publicly. Locally the console opens straight up.
    if REQUIRE_LOGIN and not require_login():
        return
    # No landing screen — the console opens on the dashboard with the sample
    # portfolio already ingested. Data is swapped from the Data page instead.
    if "results" not in st.session_state:
        st.session_state.results = _parse_samples()
    render_dashboard(st.session_state.get("results") or [])


main()
