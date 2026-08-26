"""Explainable-AI layer: recommendations and an executive narrative.

Two tiers, matching the patent's "explainable AI + decision support" claim:

* `portfolio_recommendations` — deterministic, driver-aware next-actions derived
  from each project's metrics. Always available (no network, no key), so every
  project in the table carries an AI-generated recommendation.
* `executive_narrative` — a live Gemma 4 synthesis of the whole portfolio, using
  only the computed numbers. Falls back to a local summary when no key is set or
  the call fails. The returned dict reports which source produced the text.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

GEMMA_MODEL = "gemma-4-26b-a4b-it"
_ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMMA_MODEL}:generateContent"

_SYSTEM = (
    "You are the explainable-AI module of an enterprise project-governance "
    "platform. Given portfolio telemetry, write a concise executive briefing of "
    "4-5 sentences: state overall portfolio health, name the projects driving "
    "risk and why, and end with the single most important action. Be specific "
    "and use ONLY the numbers provided — never invent projects or metrics. "
    "Output plain prose only: no markdown, no headings, no lists, no "
    "chain-of-thought."
)


# --------------------------------------------------------------------------- #
# deterministic per-project recommendations
# --------------------------------------------------------------------------- #
def _dominant_driver(p: dict) -> tuple[str, float]:
    rc = p["risk_counts"]
    behind = max(0.0, p["expected_pct"] - p["pct_complete"])
    candidates = [
        ("schedule", p["schedule_variance_days"] / 7.0),
        ("critical", rc["Critical"] * 3.0),
        ("high", rc["High"] * 1.2),
        ("blocked", p["tasks_blocked"] * 2.0),
        ("progress", behind / 10.0),
    ]
    return max(candidates, key=lambda x: x[1])


def recommend(p: dict) -> str:
    """One specific, number-grounded next action for a single project."""
    driver, weight = _dominant_driver(p)
    rc = p["risk_counts"]
    phase, var = p["phase"], p["schedule_variance_days"]

    # Green programmes get a maintain/hold message — never an alarmist one, even
    # if a soft driver exists; the tone must match the health rating.
    if p["rag"] == "Green":
        if var > 0:
            return (f"On track overall at {p['pct_complete']:.0f}% in {phase} — absorb the "
                    f"minor {var}-day slip to protect the {p['planned_go_live']} go-live.")
        if rc["High"]:
            return (f"On track in {phase} at {p['pct_complete']:.0f}% — maintain cadence and "
                    f"keep the {rc['High']} high risk(s) under active mitigation.")
        return (f"On track in {phase} at {p['pct_complete']:.0f}% complete — "
                f"maintain cadence and protect the {p['planned_go_live']} go-live.")
    if driver == "schedule" and var > 0:
        return (f"Forecast slips {var} days past plan — re-baseline the go-live and "
                f"compress the {phase} critical path before the next gate.")
    if driver == "critical":
        return (f"{rc['Critical']} critical risk(s) open in {phase} — escalate to the "
                f"steering committee and add mitigation owners this week.")
    if driver == "blocked":
        return (f"{p['tasks_blocked']} task(s) blocked in {phase} — clear dependencies "
                f"now; each blocked gate compounds the {var}-day slip.")
    if driver == "high":
        return (f"{rc['High']} high risks concentrated in {phase} — review mitigations "
                f"and confirm contingency before committing the forecast date.")
    if driver == "progress":
        return (f"Running ~{p['expected_pct'] - p['pct_complete']:.0f} pts behind the "
                f"planned curve in {phase} — reallocate resource to recover schedule.")
    return f"Monitor {phase}; risk score {p['risk_score']} within tolerance."


def portfolio_recommendations(portfolio: dict) -> list[dict]:
    return [
        {"project": p["name"], "rag": p["rag"], "risk_score": p["risk_score"],
         "text": recommend(p)}
        for p in portfolio["projects"]
    ]


# --------------------------------------------------------------------------- #
# executive narrative (Gemma 4, with local fallback)
# --------------------------------------------------------------------------- #
def _m(v: float) -> str:
    a = abs(v)
    if a >= 1_000_000:
        return f"${v/1_000_000:.2f}M"
    if a >= 1_000:
        return f"${v/1_000:.0f}k"
    return f"${v:,.0f}"


def _fallback_narrative(portfolio: dict) -> str:
    s = portfolio["summary"]
    rag = s["rag"]
    reds = [p["name"] for p in portfolio["projects"] if p["rag"] == "Red"]
    ambers = [p["name"] for p in portfolio["projects"] if p["rag"] == "Amber"]
    lead = (f"Portfolio health is {s['portfolio_health']} across {s['project_count']} "
            f"programmes ({rag['Red']} red, {rag['Amber']} amber, {rag['Green']} green), "
            f"averaging {s['avg_complete']:.0f}% complete at an average risk score of {s['avg_risk']}.")
    drivers = ""
    if reds:
        drivers = f" {', '.join(reds)} {'is' if len(reds) == 1 else 'are'} driving portfolio risk with {s['critical_risks']} critical risk(s) open and {s['tasks_blocked']} blocked task(s)."
    elif ambers:
        drivers = f" {', '.join(ambers[:2])} require attention on schedule slippage."
    tail = (f" {s['slipping']} of {s['project_count']} programmes are forecasting late; "
            f"the nearest go-live is {s['next_go_live']}.")

    b = (portfolio.get("budget") or {}).get("summary") or {}
    cost = ""
    if b.get("approved_budget"):
        cost = (f" On cost, {b['budget_utilization']:.0f}% of the {_m(b['approved_budget'])} approved budget is consumed "
                f"against a forecast at completion of {_m(b['eac'])}")
        if b.get("forecast_variance", 0) < 0:
            cost += f", {_m(-b['forecast_variance'])} over"
        cost += "."
        if b.get("projected_breach_count"):
            n = b["projected_breach_count"]
            cost += f" {n} programme{'s are' if n > 1 else ' is'} forecast to exhaust its budget before the work completes."

    return (lead + drivers + tail + cost +
            " Recommended action: prioritise the red programmes' critical-path gates, re-baseline their go-live dates, "
            "and re-estimate the remaining work where the cost forecast is breaching.")


def _budget_line(portfolio: dict) -> str:
    """One line of cost context for the narrative, when a budget is available."""
    b = (portfolio.get("budget") or {}).get("summary") or {}
    if not b.get("approved_budget"):
        return ""
    parts = [
        f"Budget: {b['approved_budget']:,.0f} approved, {b['actual_spend']:,.0f} spent "
        f"({b['budget_utilization']:.0f}% utilised), forecast at completion {b['eac']:,.0f}, "
        f"variance {b['forecast_variance']:,.0f}, budget health {b['budget_health']}."
    ]
    if b.get("projected_breach_count"):
        parts.append(f"{b['projected_breach_count']} programme(s) are forecast to exhaust their budget before completion.")
    return " ".join(parts)


def _build_prompt(portfolio: dict) -> str:
    s = portfolio["summary"]
    lines = [
        f"Portfolio: {s['project_count']} programmes. Health {s['portfolio_health']}. "
        f"RAG red/amber/green = {s['rag']['Red']}/{s['rag']['Amber']}/{s['rag']['Green']}. "
        f"Avg complete {s['avg_complete']}%. Avg risk {s['avg_risk']}. "
        f"Slipping {s['slipping']}. Critical risks {s['critical_risks']}. "
        f"Blocked tasks {s['tasks_blocked']}. Next go-live {s['next_go_live']}.",
    ]
    bl = _budget_line(portfolio)
    if bl:
        lines.append(bl)
    lines.append("Projects:")
    for p in portfolio["projects"]:
        lines.append(
            f"- {p['name']}: {p['rag']}, risk {p['risk_score']}, phase {p['phase']}, "
            f"{p['pct_complete']}% complete, schedule variance {p['schedule_variance_days']}d, "
            f"crit/high risks {p['risk_counts']['Critical']}/{p['risk_counts']['High']}, "
            f"blocked {p['tasks_blocked']}."
        )
    return "\n".join(lines)


def _gemma_call(prompt: str, api_key: str, timeout: int = 120) -> str:
    url = _ENDPOINT + "?key=" + urllib.parse.quote(api_key)
    body = {
        "systemInstruction": {"parts": [{"text": _SYSTEM}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        # gemma-4-26b-a4b-it always reasons before answering (~5k thinking tokens)
        # and does not support a thinking budget, so the cap must sit well above
        # the hidden chain-of-thought or the visible answer comes back empty.
        "generationConfig": {"temperature": 0.5, "maxOutputTokens": 8192},
    }
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    cand = (data.get("candidates") or [{}])[0]
    parts = ((cand.get("content") or {}).get("parts")) or []
    # Gemma emits chain-of-thought as parts flagged thought=true — drop them.
    text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
    if not text:
        raise RuntimeError("Empty response from Gemma")
    return text


def executive_narrative(portfolio: dict, api_key: str = "") -> dict:
    """Return {'text', 'source'} — 'gemma' when live, else 'fallback'."""
    if api_key:
        try:
            return {"text": _gemma_call(_build_prompt(portfolio), api_key), "source": "gemma"}
        except Exception as exc:  # network / quota / key — degrade gracefully
            return {"text": _fallback_narrative(portfolio), "source": "fallback",
                    "error": str(exc)[:160]}
    return {"text": _fallback_narrative(portfolio), "source": "fallback"}
