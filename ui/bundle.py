"""Assemble the embedded Meridian Governance Console into one HTML string.

The UI is the Meridian design (a self-contained HTML/CSS/JS + Plotly app, see
ui/meridian.html) served inside Streamlit via components.html. This injects the
Gemini API key (for the live Gemma narrative) and the access password (checked
by the in-app login gate).
"""
from __future__ import annotations

from pathlib import Path

UI_DIR = Path(__file__).resolve().parent


def render_app_html(gemini_key: str = "", app_password: str = "") -> str:
    html = (UI_DIR / "meridian.html").read_text(encoding="utf-8")
    html = html.replace("__GEMINI_KEY__", gemini_key or "")
    html = html.replace("__APP_PASSWORD__", app_password or "")
    return html
