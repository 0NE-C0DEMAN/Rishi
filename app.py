"""Meridian Governance Console — Streamlit host for the embedded console.

The rich UI is the Meridian design (ui/meridian.html): a multi-screen
governance app (Login → Overview · Data Ingestion · Governance Console) with
its own login gate, rendered full-bleed inside Streamlit via an iframe. This
module just configures the page and injects the access password + Gemini key.

Run locally:  streamlit run app.py
"""
from __future__ import annotations

import os

import streamlit as st
import streamlit.components.v1 as components

from ui.bundle import render_app_html

st.set_page_config(
    page_title="Meridian — Governance Console",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Strip all Streamlit chrome so the embedded console fills the page.
st.markdown(
    """
    <style>
      #MainMenu, header[data-testid="stHeader"], footer {visibility: hidden; height: 0;}
      .block-container {padding: 0 !important; max-width: 100% !important;}
      [data-testid="stAppViewContainer"], .stApp {background: #0b0f14;}
      [data-testid="stMain"] {padding: 0 !important;}
      [data-testid="stDecoration"] {display: none;}
      iframe {display: block;}
    </style>
    """,
    unsafe_allow_html=True,
)


def _secret(key: str, env: str, default: str = "") -> str:
    """Read a value from Streamlit secrets, falling back to an env var."""
    try:
        val = st.secrets[key]
        if val:
            return val
    except Exception:
        pass
    return os.environ.get(env, default)


html = render_app_html(
    gemini_key=_secret("gemini_api_key", "GEMINI_API_KEY"),
    app_password=_secret("app_password", "APP_PASSWORD"),
)
components.html(html, height=1180, scrolling=True)
