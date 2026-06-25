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
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Collapse default Streamlit chrome so the embedded console is full-bleed.
st.markdown(
    """
    <style>
      #MainMenu, header[data-testid="stHeader"], footer {visibility: hidden; height: 0;}
      .block-container {padding: 0 !important; max-width: 100% !important;}
      [data-testid="stAppViewContainer"], .stApp {background: #0b0f17;}
      [data-testid="stDecoration"] {display: none;}
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
        st.markdown("### 🛰️ Governance Intelligence Console")
        st.caption("Restricted simulation sandbox — enter the access password to continue.")
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
