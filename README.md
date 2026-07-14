# AI-Driven Project Governance Platform

An executive decision-support prototype that turns an uploaded **project plan** into
**portfolio governance intelligence**. It implements the client's workflow end to end:

```
Upload Project Plan → Data Validation → AI Analysis → Executive Dashboard
   └── Portfolio · Risks · Go-Live · Resources · Milestones · AI Insights · Reports
```

A project-plan workbook (the WBS delivery template) is parsed and normalized by a
cached Pandas engine, which derives per-project **phase, % complete, RAG health,
risk score, planned/forecast go-live, schedule variance, owner**, and
**AI-generated recommendations**. Runs on **simulated mock data** — no production
systems are connected.

> Simulation sandbox. Deliverables are a Work Made for Hire. All visuals are illustrative.

## How it maps to the patent

| Patent capability | In the app |
|---|---|
| **Data ingestion** | Upload one or more project-plan workbooks (`.xlsx`), or load the sample portfolio. |
| **Data normalization** | `governance/ingest.py` parses the metadata block + task table into a canonical schema, tolerant of the template's irregular layout. |
| **Governance intelligence** | `governance/metrics.py` computes RAG health, a 0–100 risk score, schedule variance, and phase rollups per project, then aggregates the portfolio. |
| **Explainable AI** | `governance/ai.py` produces driver-aware recommendations per project and a live **Gemma 4** executive narrative (local synthesis fallback). |
| **Executive decision support** | A seven-section dashboard: Portfolio, Risks, Go-Live, Resources, Milestones, AI Insights, Reports (with CSV/XLSX export). |

## Dashboard sections

| Section | What it shows |
|---|---|
| **Portfolio** | KPI band (health, avg risk, % complete, slipping, critical risks), the portfolio table with RAG pills, progress, variance and a one-line AI recommendation per programme, plus a health-mix donut and risk-by-programme bar. |
| **Risks** | Risk register ranked by exposure (severity × open), counts by level, exposure by programme. |
| **Go-Live** | Planned-vs-forecast dumbbell timeline and a variance table (on plan / slipping / at risk). |
| **Resources** | Task load by team and by owner (open vs critical-path), owner allocation table. |
| **Milestones** | Gate + critical-path tracker with overdue flags, and per-project phase progress. |
| **AI Insights** | The executive narrative (instant local synthesis; regenerate live with Gemma 4) and the recommendation cards. |
| **Reports** | Normalized portfolio preview and CSV / multi-sheet XLSX exports. |

## Risk & RAG model

Per project, `risk_score` (0–100) blends schedule variance, the risk-level mix
(medium/high/critical), blocked tasks, and progress behind the planned curve. RAG:

- **Red** — risk ≥ 60, or forecast slips > 21 days, or a critical risk coincides with a blocked task.
- **Amber** — risk ≥ 38, or slip > 10 days, or ≥ 2 blocked, or any critical, or ≥ 2 high risks.
- **Green** — otherwise (on plan / within tolerance).

## The project-plan template

The parser reads the client's WBS template: a metadata block (Project ID/Name,
Planned & Forecast Go-Live, Owner, Stakeholder, PM) plus a task table across
seven phases — Initiation, Requirements, Design, Development, Testing,
Implementation, Go Live — with Owner, Team, Status, % Complete, Priority, Critical
path, Dependency, Risk Level, and planned/actual start & finish dates. The template
ships blank; `governance/samples.py` generates filled example plans for the demo.

## Project structure

```
app.py                     Executive governance dashboard (upload → validate → analyze → dashboard)
console_app.py             Legacy Meridian telemetry console (previous milestone, kept for reference)
governance/
  plan_spec.py             Template structure: phases, activities, column matchers
  ingest.py                Parse + normalize a plan workbook -> ParsedPlan (+ validation report)
  metrics.py               RAG, risk score, schedule variance, portfolio + tab datasets
  ai.py                    Driver-aware recommendations + Gemma 4 executive narrative
  samples.py               Generate filled sample plans -> data/samples/*.xlsx
ui/
  exec_ui.py               Design system (palette/CSS), HTML builders, Plotly charts
  meridian.html            Legacy console UI (used by console_app.py)
data/
  samples/                 Generated sample project plans
requirements.txt  Dockerfile  docker-compose.yml  .dockerignore
```

## Run locally

```bash
pip install -r requirements.txt
python -m governance.samples                                   # generate sample plans (once)
cp .streamlit/secrets.toml.example .streamlit/secrets.toml     # set a password (+ optional Gemini key)
streamlit run app.py
```

Open http://localhost:8501, sign in with the password from `secrets.toml`, then
**upload a project plan** or click **Load sample portfolio**.

## Run with Docker

```bash
docker-compose up                                              # default password demo123
APP_PASSWORD=your-pass GEMINI_API_KEY=your-key docker-compose up --build
```

Serves on **port 8501**. Secrets and any files under `resources/` are excluded via `.dockerignore`.

## Configuration

| Setting | Streamlit secret | Env fallback | Purpose |
|---|---|---|---|
| Access password | `app_password` | `APP_PASSWORD` | Login gate |
| Gemini API key | `gemini_api_key` | `GEMINI_API_KEY` | Live Gemma 4 narrative (optional) |

The live narrative uses `gemma-4-26b-a4b-it` via the Google Generative Language API,
called server-side. The model reasons before answering and cannot have that
suppressed, so a live call takes ~60–90s; the dashboard shows an instant local
synthesis by default and only calls Gemma on demand.
