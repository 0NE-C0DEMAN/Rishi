# Meridian — Governance Console

An interactive enterprise dashboard prototype that simulates an **AI-driven project-governance platform** for enterprise IT delivery. A Streamlit app hosts a self-contained multi-screen web console (HTML/CSS/JS + Plotly.js, no build step) and feeds it telemetry from a cached Pandas pipeline. Runs entirely on **simulated, anonymized mock data** — no production systems are connected.

> Simulation sandbox. Deliverables are a Work Made for Hire. All visuals are illustrative.

## Screens

| Screen | What it does |
|---|---|
| **Login** | Access gate — validates the configured password (any email accepted in the sandbox). |
| **Overview** | Portfolio of six programmes with live risk posture, breach/watch status, an attention list, and ingestion stats. |
| **Data Ingestion** | Upload dropzone for batch exports, recent-ingestion list, and live connector tiles (Jira, Azure DevOps, Splunk, GitHub, …). Ingesting a batch nudges the governance model. |
| **Governance Console** | The core 4-zone dashboard: KPI cards with deltas + sparklines, the composite-risk timeline with the **55% action threshold**, simulation controls, and explainable diagnostics. |

## The closed loop (TRD Task 3)

Move the **simulation controls** (latency factor, ingestion-load factor, risk-sensitivity factor) — or hit the **Normal / Risk breach** scenario toggle — and the model re-scores every day of the timeline instantly. When composite risk crosses **55%**: the chart line turns **red** above the threshold, the status bar and KPI flip to breach state, and the **Diagnostics** tab populates explainable root-cause findings (driver, phase, confidence) plus a recommended mitigation.

The **AI Narrative** card generates a live root-cause synthesis with **Gemma 4** (`gemma-4-26b-a4b-it` via the Google Gemini API, called client-side; the model's chain-of-thought parts are stripped before display). Without a key configured it falls back to a local template — the card's meta label shows which one produced the text.

## Data pipeline (TRD Task 2)

Telemetry comes from `data/mock_logistics_data.csv` (columns: `Timestamp, Ingested_Log_Volume, Baseline_Schema_Latency_ms, Phase_ID`; 75 daily records across five delivery phases, regenerable with `python data/generate_mock.py`).

`data/pipeline.py` ingests and normalizes it with Pandas, cached with `@st.cache_data` (re-parsed only when the file changes). The host injects the normalized records into the console as JSON; the in-browser governance model scores risk from those records so the sliders respond with zero server round-trips. `window.__DATA_SOURCE__` in the page reports `csv-pipeline` (or `fallback-generator` if the CSV is unavailable).

Risk model (client-side, per day): `risk = clamp(50·(0.42·latencyₙ + 0.28·loadₙ + 0.30·schedule) · sensitivity, 0, 100)` with the action threshold at **55%**.

## Project structure

```
app.py                     Streamlit host: page config, secrets, CSV payload injection
data/
  generate_mock.py         Deterministic generator for the mock CSV
  mock_logistics_data.csv  Mock telemetry (the TRD tracking fields)
  pipeline.py              @st.cache_data ingest + Pandas normalization + payload
ui/
  meridian.html            The Meridian console (all screens, styles, model, charts)
  bundle.py                Injects the CSV payload, Gemini key, and access password
.streamlit/
  config.toml              Server config
  secrets.toml.example     Template for the secrets
requirements.txt  Dockerfile  docker-compose.yml  .dockerignore
DESIGN_BRIEF.md            The greenfield design brief the UI was built from
```

## Run locally

```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # set a password (+ optional Gemini key)
streamlit run app.py
```

Open http://localhost:8501 and sign in with the password from `secrets.toml`.

## Run with Docker (TRD Task 4)

Single command (default password `demo123`):

```bash
docker-compose up
```

With a real password and the live AI narrative:

```bash
APP_PASSWORD=your-password GEMINI_API_KEY=your-gemini-key docker-compose up --build
```

Serves on **port 8501**. Secrets and any files under `resources/` are excluded from the image via `.dockerignore`.

## Deploy to Streamlit Community Cloud

1. Push this repo to GitHub and create a new app pointing at `app.py`.
2. In **App → Settings → Secrets** add:
   ```toml
   app_password = "your-strong-password"
   gemini_api_key = "your-gemini-key"   # optional — enables the live AI narrative
   ```
3. Deploy. Only visitors with the password can enter the console.

## Configuration

| Setting | Streamlit secret | Env fallback | Purpose |
|---|---|---|---|
| Access password | `app_password` | `APP_PASSWORD` | Login gate |
| Gemini API key | `gemini_api_key` | `GEMINI_API_KEY` | Live Gemma 4 narrative (optional) |

## Customization

- **Data** — drop in a different `data/mock_logistics_data.csv` with the same columns (any number of rows/phases; the console derives the phase bands from `Phase_ID`).
- **Threshold / weights** — the risk model constants live in the model section of `ui/meridian.html` (`THRESHOLD`, `K`, `W_LAT`, `W_LOAD`, `W_SCHED`).
- **Branding / palette** — design tokens are CSS variables at the top of `ui/meridian.html`.
