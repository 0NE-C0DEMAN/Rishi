# Handover — AI-Driven Project Governance Platform

Everything needed to run, deploy, and take ownership of this application. Technical detail lives in [README.md](README.md); this document covers what a new owner needs to know before running it in their own environment.

---

## 1. What this is

A working prototype of an **AI-driven project governance platform**. It takes a project-plan workbook, normalizes it, scores delivery risk, and presents an executive dashboard:

```
Upload a project plan → validate → AI analysis → executive dashboard
```

It accepts two plan layouts (the WBS delivery template and a Microsoft Planner / Project export), tracks cost as well as schedule, and lets the plan data be edited in place with every figure recomputing from the change.

It demonstrates the five capabilities in the patent concept — data ingestion, data normalization, governance intelligence, explainable AI, and executive decision support — end to end, on realistic but simulated data.

**Deliverable status:** feature-complete and verified. See section 7 for known limitations, stated plainly.

---

## 2. Running it

### Locally

```bash
pip install -r requirements.txt
python -m governance.samples     # writes the four sample plans (once)
streamlit run app.py
```

Opens at http://localhost:8501 on the dashboard, with the sample portfolio already loaded. Requires Python 3.10 or newer.

### With Docker

```bash
docker-compose up
```

Serves on port 8501.

> **Note:** the Docker files are written and reviewed but have **not been executed** on this project, as there was no Docker daemon on the development machine. Expect to run `docker-compose up --build` once and resolve any first-run issue. The image is a standard `python:3.11-slim` plus `requirements.txt` build; nothing exotic.

---

## 3. Deploying to Streamlit Community Cloud

1. Push this repository to GitHub (see section 6 for the ownership transfer).
2. At https://share.streamlit.io, create an app pointing at **`app.py`** on the `main` branch.
3. Open **App → Settings → Secrets** and paste:

   ```toml
   require_login = true
   app_password  = "choose-a-strong-password"
   gemini_api_key = "your-google-ai-studio-key"   # optional
   ```

4. Deploy.

### Important: the access gate

`require_login` defaults to **false**, so the app opens straight onto the dashboard. That is convenient locally and **wrong for a public URL** — without it, anyone with the link can open the app. **Set `require_login = true` before or at the moment you deploy.** With the gate on, visitors get a password screen; any email is accepted, only the password is checked.

---

## 4. Configuration reference

| Setting | Secret key | Env var | Default | Purpose |
|---|---|---|---|---|
| Access gate | `require_login` | `REQUIRE_LOGIN` | `false` | Put the password screen in front of the app |
| Access password | `app_password` | `APP_PASSWORD` | `demo123` | Checked when the gate is on |
| Gemini API key | `gemini_api_key` | `GEMINI_API_KEY` | empty | Enables the live Gemma 4 narrative |

Locally these live in `.streamlit/secrets.toml`, which is git-ignored. Copy `.streamlit/secrets.toml.example` to start. **Change `app_password` from the default before any deployment.**

---

## 5. What is real and what is simulated

Being explicit here matters, because this is a prototype.

**Real:**

- **Workbook parsing.** `governance/ingest.py` reads an actual `.xlsx` project plan, locates the metadata block and task table by content rather than fixed positions, normalizes every field, and reports what was missing.
- **All governance calculations.** RAG health, the 0-100 risk score, schedule variance, phase rollups, the risk register, resource load and the milestone tracker are computed in Pandas from the uploaded data (`governance/metrics.py`).
- **The cost model.** Budget utilisation, remaining budget, forecast at completion, forecast variance, cost vs progress and the projected breach point are computed from the plan's own effort and completion (`governance/budget.py`).
- **Editing.** Cell edits on the Data page are applied by the engine, and every figure on every page recomputes from them.
- **The AI narrative.** The *Generate with Gemma 4* button performs a real call to Google's Generative Language API using `gemma-4-26b-a4b-it`.
- **CSV exports**, generated from the same normalized dataset the screen renders.

**Simulated:**

- **The data.** The four sample programmes (Atlas, Orion, Helios, Vega) are generated fixtures, not real projects. Replace them by uploading real plans on the Data page.
- **Budget figures, unless the plan states them.** Neither plan format is guaranteed to carry cost columns, so where none are supplied the approved budget and spend are *estimated* from effort at a blended rate of $85/h. A real figure always wins: enter it on the Data page, or add an "Approved Budget" row to the plan's metadata block. Until then, treat the cost figures as an illustration of the model rather than the client's actual finances.
- **The risk model** is a deterministic, explainable formula, not a trained ML model. It is transparent and tunable, and it is the natural place to substitute a real model later. Its thresholds are documented in the README and surfaced in-app under "How to read this dashboard".
- **The per-project recommendations** are driver-aware templates, selected by whichever factor dominates that programme. Only the executive narrative uses a live language model.

No production systems, live project tools, or customer data are connected.

---

## 6. Repository and ownership

- Code currently lives at **github.com/0NE-C0DEMAN/Rishi** (private).
- To transfer: **GitHub → Settings → Danger Zone → Transfer ownership**, or add the client as owner of a fresh repository and push to it.
- **Never committed:** `.streamlit/secrets.toml`, the `resources/` folder (which contains the client's personal documents), the design-handoff bundle, and `node_modules/`. These are listed in `.gitignore` and were verified absent from every push.
- Deliverables are a **Work Made for Hire**; on final payment the client owns the code outright.

### API key note

The Gemini key used during development belongs to the developer and is **not** included in the repository. The client should generate their own key at https://aistudio.google.com/apikey and add it to the deployment secrets. The app runs fully without a key — the AI Insights page falls back to the built-in local synthesis, clearly labelled as such in the interface.

---

## 7. Known limitations

Stated plainly so there are no surprises.

1. **Docker is untested.** Written and reviewed, never executed. See section 2.
2. **No dark mode.** The app is light-theme only. Design tokens are centralised at the top of `ui/dashboard.src.html`, so adding a dark palette is a contained change, but it is not built.
3. **The live Gemma narrative takes 60 to 90 seconds.** The model reasons before answering and that cannot be disabled for this model. The dashboard shows an instant local synthesis by default and only calls the live model on demand, with an elapsed-seconds counter so the wait is visible rather than looking frozen.
4. **Mobile is functional, not polished.** Layouts collapse and nothing overflows horizontally down to 390px wide, but the app is designed for desktop use.
5. **The blank template parses to an empty portfolio.** The original `Project Plan Template.xlsx` ships with placeholder cells only, so uploading it yields zero programmes. This is correct behaviour; use a filled plan.
6. **Single-user, no persistence.** Uploaded plans and any edits live in the Streamlit session only. Refreshing, or a second visitor, resets to the sample portfolio. There is no database or user-account system, so edits are not shared between people and do not survive a restart. Export from the Reports page to keep a copy.

---

## 8. Changing the app

### The dashboard UI

The interface is a self-contained React app embedded in Streamlit. **Edit `ui/dashboard.src.html`** (the JSX source), then rebuild:

```bash
cd scripts && npm i react@18 react-dom@18 @babel/standalone   # once
node scripts/build_dashboard.mjs                              # after each edit
```

That compiles the JSX and inlines React into `ui/dashboard.html`, the file the app actually serves. **Editing `ui/dashboard.html` directly will be overwritten** by the next build.

### Common changes

| To change | Edit |
|---|---|
| Colours, fonts, spacing | The `:root` token block at the top of `ui/dashboard.src.html` |
| RAG thresholds, risk weighting | `_rag()` and `_risk_score()` in `governance/metrics.py` |
| Recommendation wording | `recommend()` in `governance/ai.py` |
| Accepted plan structure | `governance/plan_spec.py` (WBS) and `governance/planner.py` (Planner export) |
| Blended hourly rate, cost thresholds | `governance/budget.py` |
| Which fields users may edit | `EDITABLE_FIELDS` in `app.py` |
| Sample data | `governance/samples.py`, then `python -m governance.samples` |

---

## 9. First-run checklist

- [ ] `pip install -r requirements.txt` succeeds on Python 3.10 or newer
- [ ] `python -m governance.samples` creates `data/samples/*.xlsx`
- [ ] `streamlit run app.py` opens the dashboard showing four programmes
- [ ] Uploading a filled project plan on the **Data** page replaces the portfolio
- [ ] `require_login = true` is set before the app is publicly reachable
- [ ] `app_password` is changed from `demo123`
- [ ] A Gemini API key is added if the live narrative is wanted
