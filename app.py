"""Governance Intelligence Console — Streamlit host + password gate.

Run locally:   streamlit run app.py
The rich UI is an embedded React app (see ui/); this module only handles the
page shell, the access-password gate, and feeding normalized mock data in.
"""
from __future__ import annotations

import os

import streamlit as st
import streamlit.components.v1 as components

from data.pipeline import build_payload, load_governance_data
from ui.bundle import render_app_html

st.set_page_config(
    page_title="Governance Intelligence Console",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Collapse default Streamlit chrome so the embedded console is full-bleed.
st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
      #MainMenu, header[data-testid="stHeader"], footer {visibility: hidden; height: 0;}
      .block-container {padding: 0 !important; max-width: 100% !important;}
      [data-testid="stAppViewContainer"], .stApp {background: #0b0f14;}
      [data-testid="stDecoration"] {display: none;}
      html, body, [class*="css"] {font-family: 'Inter', sans-serif;}
      [data-testid="stTextInput"] input {
        background: #121821 !important; border: 1px solid #223042 !important;
        color: #e6edf3 !important; border-radius: 8px !important; height: 46px;
      }
      [data-testid="stTextInput"] input:focus {
        border-color: #d4a85a !important; box-shadow: 0 0 0 1px rgba(212,168,90,0.3) !important;
      }
      .stButton button {
        background: #d4a85a !important; color: #0b0f14 !important; border: none !important;
        font-weight: 600 !important; border-radius: 8px !important; height: 46px;
        transition: background 0.14s ease;
      }
      .stButton button:hover {background: #e8d4a8 !important;}
    </style>
    """,
    unsafe_allow_html=True,
)


def _expected_password() -> str | None:
    # Prefer Streamlit secrets (Cloud); fall back to APP_PASSWORD env (Docker).
    try:
        val = st.secrets["app_password"]
        if val:
            return val
    except Exception:
        pass
    return os.environ.get("APP_PASSWORD")


def _gemini_key() -> str:
    """Gemini API key for the embedded Gemma client (Streamlit secrets or env)."""
    try:
        val = st.secrets["gemini_api_key"]
        if val:
            return val
    except Exception:
        pass
    return os.environ.get("GEMINI_API_KEY", "")


def require_login() -> bool:
    """Gate the console behind the configured access password."""
    if st.session_state.get("auth_ok"):
        return True

    expected = _expected_password()
    st.markdown("<div style='height: 9vh'></div>", unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 1.15, 1])
    with mid:
        st.markdown(
            "<div style='font-family:Inter,sans-serif;margin-bottom:22px'>"
            "<div style='width:38px;height:38px;border-radius:9px;display:grid;"
            "place-items:center;background:#1b2532;border:1px solid rgba(212,168,90,0.32);"
            "margin-bottom:16px'><svg viewBox='0 0 24 24' width='19' height='19' fill='none' "
            "stroke='#d4a85a' stroke-width='1.75' stroke-linecap='round' stroke-linejoin='round'>"
            "<path d='M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z'/>"
            "</svg></div>"
            "<div style='font-size:10px;letter-spacing:1.6px;text-transform:uppercase;"
            "color:#8493a3;font-weight:600'>Restricted · Simulation sandbox</div>"
            "<div style='font-size:23px;font-weight:600;color:#e6edf3;margin-top:8px;"
            "letter-spacing:-0.02em'>Governance Intelligence Console</div>"
            "<div style='font-size:13px;color:#8493a3;margin-top:8px'>"
            "Enter the access password to continue.</div></div>",
            unsafe_allow_html=True,
        )
        if expected is None:
            st.error(
                "No access password configured. Set `app_password` in "
                "`.streamlit/secrets.toml` (local) or in App → Settings → Secrets "
                "(Streamlit Community Cloud)."
            )
            return False
        pw = st.text_input(
            "Access password", type="password",
            label_visibility="collapsed", placeholder="Access password",
        )
        if st.button("Enter console", type="primary", use_container_width=True):
            if pw == expected:
                st.session_state["auth_ok"] = True
                st.rerun()
            else:
                st.error("Incorrect password.")
    return False


if not require_login():
    st.stop()

df = load_governance_data()
payload = build_payload(df)
components.html(render_app_html(payload, _gemini_key()), height=1180, scrolling=True)
