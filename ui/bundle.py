"""Assemble the embedded Meridian Governance Console into one HTML string.

The UI is the Meridian design (a self-contained HTML/CSS/JS + Plotly app, see
ui/meridian.html) served inside Streamlit via components.html. This injects:

  * the telemetry payload from the cached Pandas CSV pipeline (TRD Task 2) —
    the in-browser governance model consumes these records directly;
  * the Gemini API key for the live Gemma narrative;
  * the access password checked by the in-app login gate.
"""
from __future__ import annotations

import json
from pathlib import Path

UI_DIR = Path(__file__).resolve().parent


def render_app_html(
    gemini_key: str = "",
    app_password: str = "",
    data: dict | None = None,
) -> str:
    html = (UI_DIR / "meridian.html").read_text(encoding="utf-8")
    html = html.replace("__GEMINI_KEY__", gemini_key or "")
    html = html.replace("__APP_PASSWORD__", app_password or "")
    if data:
        # Replaces the quoted placeholder so CSV_DATA becomes a real JS object.
        html = html.replace('"__CSV_DATA__"', json.dumps(data))
    return html


def render_dashboard_html(payload: dict, gemini_key: str = "") -> str:
    """Inject the computed governance payload into the React dashboard embed.

    The React app (ui/dashboard.html) is fully self-contained; Streamlit runs
    the Pandas engine, hands it the portfolio JSON, and hosts it full-bleed.
    """
    html = (UI_DIR / "dashboard.html").read_text(encoding="utf-8")
    html = html.replace("__PAYLOAD__", json.dumps(payload))
    html = html.replace("__GEMINI_KEY__", gemini_key or "")
    return html
