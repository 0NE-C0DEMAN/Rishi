# Design Brief — Project Governance Console (prototype)

> Greenfield design brief for a senior product/UI designer. **There is no existing design to follow, preserve, or reference — define the entire visual language yourself.** This document describes *what the product must do and contain*, not how it should look or be laid out.

## 1. What this is

A web dashboard for a simulated **AI-driven project-governance platform** that monitors and de-risks enterprise IT delivery. It continuously reads project telemetry, scores delivery risk against a threshold, and surfaces **explainable** root-cause diagnostics and recommended actions. This build is a **prototype / demo running on simulated (mock) data** — a visually convincing console, not a production system.

## 2. Who uses it

Senior IT project and delivery managers, and enterprise stakeholders. It will be shown in live demos and to executives, so it must read as a **premium, trustworthy, enterprise-grade product** — the kind of polished console a serious analytics or institutional-monitoring vendor would ship.

## 3. Design goals

- Communicate delivery risk **at a glance**, then let the user drill in.
- Feel **calm, precise, and authoritative** — information-dense but never cluttered.
- Read as **genuinely and deliberately designed** — a cohesive system of color, type, spacing, and components, not a framework default or a template.
- Quality bar: match the *craft level* of best-in-class analytics, observability, and financial-terminal products. Match that quality, not their specific looks.

## 4. What the user must be able to do (functional needs — not a layout)

1. **Scan headline health.** A small set of key indicators, each with a current value and its movement versus a baseline: an overall/composite risk score, schedule adherence, a processing-latency measure, and an ingestion-throughput measure.
2. **Read risk over time.** A time-series view of risk across the project timeline, with a clearly marked **action threshold**. It must be immediately obvious whether risk is below the line (healthy) or above it (breach), and the view should visibly change state on a breach.
3. **Drive a simulation.** Adjust a few input controls (e.g. a latency factor, an ingestion-load factor, and a risk-sensitivity factor) and see the indicators and the trend respond **immediately**.
4. **Get explainable diagnostics.** When risk crosses the threshold, a feed of root-cause findings appears: what is driving the risk, which project phase is most affected, a confidence level, and a recommended action. One of these items is an **AI-generated narrative** (a few sentences) produced on demand.
5. Always understand, unobtrusively, that this is a **simulation sandbox running on mock data**.

How all of this is arranged, grouped, themed, and styled is **entirely the designer's decision** (see §7).

## 5. The data (use realistic values in any mockups)

Time series — one record per day over roughly 2.5 months, spanning about five sequential project phases:

| Field | Example |
|---|---|
| Timestamp | 2026-03-01 … 2026-05-14 (daily) |
| Ingested log volume | ~95–135 (count) |
| Schema latency | ~0.5–1.4 ms (drifts upward in later phases) |
| Phase | P-01 Discovery, P-02 Design, P-03 Build, P-04 Integrate, P-05 Stabilize |

Derived for display: a composite risk score 0–100% with an **action threshold at 55%**; schedule adherence %; average latency (ms); throughput. Diagnostics are severity-tagged items (e.g. critical / watch / nominal), each with a short title, a one-to-three-sentence body, and a few metadata fields such as driver, phase, and confidence.

## 6. Content the UI must accommodate

- A compact set of headline metric readouts (value plus delta/trend indicator).
- One primary time-series chart with a threshold reference line and a distinct **breach state** (a clear visual shift when risk is above the threshold).
- A small control surface with three adjustable inputs.
- A diagnostics/alert feed of severity-tagged items — including an AI-generated narrative item and a recommended-action item.
- Light product identity: a name, and a subtle "simulation sandbox / mock data" marker.

## 7. Visual direction — open

Define the complete visual language yourself: light or dark, the color system, typography, layout structure, information density, and motion. Make confident, intentional choices. Color should be used **meaningfully** (status and severity), not decoratively. Typography should carry a clear hierarchy. Spacing and alignment should feel engineered. Tone words to aim for: professional, precise, premium, trustworthy, modern, restrained.

## 8. Constraints (implementation reality)

- It will be delivered as a **self-contained web front-end** (HTML + CSS + vanilla JS, or React loaded from a CDN — **no build step**), embedded inside a Streamlit app. Design for the **web**, as a single dashboard screen (internal scrolling is acceptable). No native-app or OS window chrome.
- Charts are rendered with a JavaScript charting library (Plotly.js is available; any CDN-loaded library is acceptable).
- Reasonable responsiveness: it should look right at roughly 1280–1600px wide and degrade gracefully on narrower screens.

## 9. Avoid

Emojis; generic "AI-slop" aesthetics (default purple gradients, clip-art, decorative blobs, stock-y illustrations); heavy or garish color blocking; visual clutter; and anything that looks like an out-of-the-box framework theme.

## 10. Deliverable

A single, self-contained **HTML file** (inline CSS and JS, realistic inline sample data, charts actually rendered) that demonstrates the full dashboard in **both the normal state and the risk-breach state** (via a toggle, or shown as two sections). It should be visually final — a design that could be adopted directly — and expose its palette and type scale as CSS variables so it can be implemented faithfully.
