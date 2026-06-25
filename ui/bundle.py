"""Assemble the embedded React app into a single self-contained HTML string.

The UI is delivered to Streamlit via ``components.html``. Because that renders
inside a sandboxed iframe, relative ``<link>``/``<script src>`` to local files
won't resolve, so we inline the CSS and JSX and inject the data payload as a
JSON literal. React, Babel and Plotly are loaded from CDNs (absolute URLs),
which keeps deployment build-step-free.
"""
from __future__ import annotations

import json
from pathlib import Path

UI_DIR = Path(__file__).resolve().parent


def render_app_html(payload: dict, gemini_key: str = "") -> str:
    template = (UI_DIR / "template.html").read_text(encoding="utf-8")
    styles = (UI_DIR / "styles.css").read_text(encoding="utf-8")
    gemma_js = (UI_DIR / "gemma.js").read_text(encoding="utf-8")
    app_js = (UI_DIR / "dashboard.jsx").read_text(encoding="utf-8")

    html = template.replace("/* __GOV_STYLES__ */", styles)
    html = html.replace('"__GOV_DATA__"', json.dumps(payload))
    html = html.replace("%%GEMINI_KEY%%", gemini_key or "")
    html = html.replace("/* __GOV_GEMMA__ */", gemma_js)
    html = html.replace("// __GOV_APP__", app_js)
    return html
