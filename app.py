"""Meridian Governance Console — Streamlit host for the embedded console.

The rich UI is the Meridian design (ui/meridian.html): a multi-screen
governance app (Login → Overview · Data Ingestion · Governance Console) with
its own login gate, rendered full-bleed inside Streamlit via an iframe pinned
to the viewport height, so the Meridian sidebar stays fixed and only its main
content scrolls (no page scroll).

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

# Strip Streamlit chrome, zero the page padding, and pin ONLY the iframe to the
# viewport height. (Forcing 100vh on the nested containers stacks them and
# pushes the iframe off-screen — so only the iframe gets the height.)
st.markdown(
    """
    <style>
      #MainMenu, header[data-testid="stHeader"], footer {display: none !important;}
      [data-testid="stDecoration"], [data-testid="stStatusWidget"] {display: none !important;}
      html, body {overflow: hidden !important;}
      .stApp {background: #0b0f14;}
      [data-testid="stMain"] {overflow: hidden !important;}
      .block-container, [data-testid="stMainBlockContainer"] {
        padding: 0 !important; margin: 0 !important; max-width: 100% !important;
      }
      [data-testid="stVerticalBlock"] {gap: 0 !important;}
      iframe {height: 100vh !important; width: 100% !important; display: block; border: none;}
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
components.html(html, height=900, scrolling=True)
