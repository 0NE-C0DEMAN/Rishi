# AI-Driven Project Governance Platform

An executive decision-support prototype that turns an uploaded **project plan** into
**portfolio governance intelligence**:

```
Upload a project plan → validate → AI analysis → executive dashboard
```

A project-plan workbook (the WBS delivery template) is parsed and normalized by a
Pandas engine, which derives per-project **phase, % complete, RAG health, risk
score, planned/forecast go-live, schedule variance, owner**, and **AI-generated
recommendations**. Runs on **simulated mock data** — no production systems are
connected.

> Simulation sandbox. Deliverables are a Work Made for Hire. All visuals are illustrative.

## How it maps to the patent

| Patent capability | In the app |
|---|---|
| **Data ingestion** | The **Data** page: drag-and-drop a project-plan workbook (`.xlsx`), or load the sample portfolio. |
| **Data normalization** | `governance/ingest.py` parses the metadata block and task table into a canonical schema, tolerant of the template's irregular layout, and reports field coverage per source. |
| **Governance intelligence** | `governance/metrics.py` computes RAG health, a 0–100 risk score, schedule variance and phase rollups per project, then aggregates the portfolio. |
| **Explainable AI** | `governance/ai.py` produces driver-aware recommendations per project and a live **Gemma 4** executive narrative (local synthesis fallback). |
| **Executive decision support** | Eight sections: Portfolio, Risks, Go-Live, Resources, Milestones, AI Insights, Reports, Data. |

## Architecture

Streamlit is the **host and data plane only**. The UI is a self-contained React app
embedded via `st.components.v1.html`:

- `ui/dashboard.src.html` — the app, authored in JSX (edit this one).
- `scripts/build_dashboard.mjs` — precompiles the JSX and inlines React, producing
  `ui/dashboard.html`: a single file with no runtime Babel and no CDN fetch.
- `ui/bundle.py` — injects the computed portfolio payload and the Gemini key.

The embedded app owns the only left rail; Streamlit's sidebar is hidden. Ingestion
lives on the app's Data page, which drives three off-screen Streamlit widgets (a
file input and two buttons) so parsing stays in Python.

### Editing the UI

```bash
cd scripts && npm i react@18 react-dom@18 @babel/standalone   # once
node scripts/build_dashboard.mjs                              # after each edit
```

## Dashboard sections

| Section | What it shows |
|---|---|
| **Portfolio** | Headline insight, KPI band with mini distribution charts, the programme table (search + health filter, row click opens a full breakdown), health-mix donut and risk-by-programme bars. |
| **Risks** | Risk register ranked by exposure with severity filter and search, plus exposure by programme. |
| **Go-Live** | Planned-vs-forecast timeline with the slip labelled inline, and the variance table. |
| **Resources** | Delivery load by team or owner (open vs critical-path), and owner allocation. |
| **Milestones** | Gate and critical-path tracker with status filter and search, plus per-project phase progress. |
| **AI Insights** | The executive narrative (instant local synthesis; regenerate live with Gemma 4, copy to clipboard) and the recommendation cards. |
| **Reports** | Normalized portfolio preview and timestamped CSV exports. |
| **Data** | Upload, sample loader, and the ingested-sources table with per-file validation. |

Tables freeze their first column, sort on any header, and page at a size derived
from the space available, so a screen never scrolls.

## Risk and RAG model

Per project, `risk_score` (0–100) blends schedule variance, the risk-level mix,
blocked tasks, and progress behind the planned curve. RAG:

- **Red** — risk ≥ 60, or forecast slips > 21 days, or a critical risk coincides with a blocked task.
- **Amber** — risk ≥ 38, or slip > 10 days, or ≥ 2 blocked, or any critical, or ≥ 2 high risks.
- **Green** — otherwise.

## The project-plan template

The parser reads the client's WBS template: a metadata block (Project ID/Name,
Planned and Forecast Go-Live, Owner, Stakeholder, PM) plus a task table across
seven phases — Initiation, Requirements, Design, Development, Testing,
Implementation, Go Live — with Owner, Team, Status, % Complete, Priority, Critical
path, Dependency, Risk Level, and planned/actual start and finish dates. The
template ships blank; `governance/samples.py` generates filled example plans.

## Project structure

```
app.py                     Streamlit host: engine, payload injection, host bridge
console_app.py             Legacy telemetry console (earlier milestone, kept for reference)
governance/
  plan_spec.py             Template structure: phases, activities, column matchers
  ingest.py                Parse + normalize a plan workbook (+ validation report)
  metrics.py               RAG, risk score, schedule variance, portfolio datasets
  ai.py                    Recommendations + Gemma 4 executive narrative
  samples.py               Generate sample plans -> data/samples/*.xlsx
ui/
  dashboard.src.html       The React app (JSX source — edit this)
  dashboard.html           Compiled, self-contained embed (generated)
  bundle.py                Injects the payload and the Gemini key
  meridian.html            Legacy console UI (used by console_app.py)
scripts/build_dashboard.mjs  JSX precompile + inline-React build step
data/samples/              Generated sample project plans
requirements.txt  Dockerfile  docker-compose.yml  .dockerignore
```

## Run locally

```bash
pip install -r requirements.txt
python -m governance.samples          # generate sample plans (once)
streamlit run app.py
```

Opens on the dashboard at http://localhost:8501 with the sample portfolio loaded.

## Run with Docker

```bash
docker-compose up
```

Serves on **port 8501**. Secrets and anything under `resources/` are excluded from
the image via `.dockerignore`.

## Deploy

1. Push to GitHub and point a Streamlit Community Cloud app at `app.py`.
2. In **App → Settings → Secrets**:
   ```toml
   require_login = true              # gate the public URL
   app_password = "your-strong-password"
   gemini_api_key = "your-gemini-key"   # optional — enables the live narrative
   ```

## Configuration

| Setting | Streamlit secret | Env fallback | Purpose |
|---|---|---|---|
| Access gate | `require_login` | `REQUIRE_LOGIN` | Off by default; set true before exposing the app publicly |
| Access password | `app_password` | `APP_PASSWORD` | Checked when the gate is on |
| Gemini API key | `gemini_api_key` | `GEMINI_API_KEY` | Live Gemma 4 narrative (optional) |

The live narrative uses `gemma-4-26b-a4b-it` via the Google Generative Language
API. The model reasons before answering and cannot have that suppressed, so a live
call takes roughly 60–90 seconds; the dashboard shows an instant local synthesis by
default and only calls Gemma on demand.
