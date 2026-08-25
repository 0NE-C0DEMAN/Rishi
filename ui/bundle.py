"""Assemble the embedded governance dashboard into one HTML string.

The UI is a self-contained React app (ui/dashboard.html, compiled from
ui/dashboard.src.html) served inside Streamlit via components.html. This
injects the computed portfolio payload and the Gemini API key used for the
live Gemma narrative.
"""
from __future__ import annotations

import json
from pathlib import Path

UI_DIR = Path(__file__).resolve().parent


def render_dashboard_html(payload: dict, gemini_key: str = "") -> str:
    """Inject the computed governance payload into the React dashboard embed.

    The React app (ui/dashboard.html) is fully self-contained; Streamlit runs
    the Pandas engine, hands it the portfolio JSON, and hosts it full-bleed.
    """
    html = (UI_DIR / "dashboard.html").read_text(encoding="utf-8")
    html = html.replace("__PAYLOAD__", json.dumps(payload))
    html = html.replace("__GEMINI_KEY__", gemini_key or "")
    return html
