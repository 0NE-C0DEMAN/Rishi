# Governance Intelligence Console

An interactive enterprise dashboard prototype that simulates an **AI-Driven Project Governance** platform for enterprise IT delivery. Built with Streamlit (host + access gate) and an embedded React + Plotly front-end. Runs entirely on **simulated, anonymized mock data** — no production systems are connected.

> Simulation sandbox. Deliverables are a Work Made for Hire. All visuals are illustrative.

## What it shows

The UI is organized into the four zones from the requirements, which map onto the governance pipeline:

| Zone | Dashboard | Pipeline stage |
|------|-----------|----------------|
| **Zone 1** | KPI cards — composite risk, schedule adherence, schema latency, ingestion throughput (with deltas) | Governance health |
| **Zone 2** | Full-width Plotly risk-trajectory chart; the line turns **red** when composite risk crosses the 55% threshold | Governance Intelligence (risk prediction) |
| **Zone 3** | Control sliders — latency factor, ingestion load, risk sensitivity | Simulation inputs |
| **Zone 4** | Explainable-AI root-cause diagnostic feed that populates automatically on a threshold breach | Explainable AI + Action Orchestration |

Moving the **Zone 3** sliders recomputes the governance risk model live (client-side), recolors the **Zone 2** chart, and drives the **Zone 4** alert feed — a closed interaction loop.

## Architecture

- **Streamlit** hosts the app, handles the access-password gate, and runs the Pandas data pipeline.
- The rich UI is a self-contained **React 18 app** (with **Plotly.js**) mounted via `st.components.v1.html()`. React, Babel and Plotly load from CDNs, so there is **no Node build step** — it deploys to Streamlit Community Cloud as-is.
- Python computes the normalized dataset once (`@st.cache_data`) and injects it into the React app as a JSON payload. The risk-model constants live in one place (`data/pipeline.py`) and are shared with the front-end.

## Project structure

```
app.py                     Streamlit entrypoint: password gate + mounts the React app
data/
  generate_mock.py         Deterministic generator for the mock CSV
  mock_logistics_data.csv  Mock dataset (Timestamp, Ingested_Log_Volume, Baseline_Schema_Latency_ms, Phase_ID)
  pipeline.py              Ingest + normalize (Pandas) + the governance risk model
ui/
  template.html            HTML shell (React/Babel/Plotly CDNs + injection placeholders)
  styles.css               Design system (dark enterprise theme)
  dashboard.jsx            The React dashboard (4 zones, live recompute, XAI feed)
  bundle.py                Inlines CSS/JSX + injects the data payload
.streamlit/
  config.toml              Theme + server config
  secrets.toml.example     Template for the access password
requirements.txt
Dockerfile  docker-compose.yml  .dockerignore
```

## Run locally

```bash
pip install -r requirements.txt
python data/generate_mock.py          # writes data/mock_logistics_data.csv (only needed once)
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # then set a password
streamlit run app.py
```

Open http://localhost:8501 and enter the password from `secrets.toml`.

## Deploy to Streamlit Community Cloud

1. Push this repo to GitHub.
2. Create a new app on Streamlit Cloud pointing at `app.py`.
3. In **App → Settings → Secrets**, add:
   ```toml
   app_password = "your-strong-password"
   ```
4. Deploy. Only visitors with the password can reach the console.

## Run with Docker

Single command (uses the default password `demo123`):

```bash
docker-compose up
```

Set a real password:

```bash
APP_PASSWORD=your-strong-password docker-compose up --build
```

The app is served on http://localhost:8501. The image excludes secrets and any files under `resources/` via `.dockerignore`.

## Data & risk model

The mock CSV has the columns `Timestamp, Ingested_Log_Volume, Baseline_Schema_Latency_ms, Phase_ID`. Latency drifts upward across later project phases so the threshold story is legible.

Per-day risk:

```
risk = 100 · sensitivity · (0.65 · latency_component + 0.35 · volume_component)
latency_component = clamp01((latency · latency_factor − LAT_REF) / (LAT_MAX − LAT_REF))
volume_component  = clamp01((volume · load_factor − VOL_REF) / (VOL_MAX − VOL_REF))
```

Composite risk is the mean over the most recent 10 days. A composite above **55%** raises the red-alert / XAI feed. All constants are in `data/pipeline.py` (`MODEL`).

## Customization

- **Branding** — edit the brand mark/title in `ui/dashboard.jsx` (`TopBar`) and colors in `ui/styles.css` (`:root`).
- **Data** — drop in a real `data/mock_logistics_data.csv` with the same columns, or tweak `data/generate_mock.py`.
- **Thresholds / weights** — adjust `MODEL` in `data/pipeline.py`.

## Note on the `resources/` folder

Source IP/reference documents are kept in `resources/`, which is **gitignored and dockerignored** — it must not be committed or deployed. Keep it local.
