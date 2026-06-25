"""Data ingestion + normalization + the governance risk model.

This module is the Python side of the patent pipeline:
  * Stage 1 (Ingestion)     -> ``load_raw`` reads the local mock CSV.
  * Stage 2 (Normalization) -> ``normalize`` coerces types, sorts, validates schema.
  * Stage 3 (Intelligence)  -> ``MODEL`` + ``risk_series`` define the scoring formula.

The same ``MODEL`` constants are injected into the embedded React app so the
client-side live recompute uses an identical formula (single source of truth —
no duplicated magic numbers).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

DATA_DIR = Path(__file__).resolve().parent
CSV_PATH = DATA_DIR / "mock_logistics_data.csv"

REQUIRED_COLUMNS = [
    "Timestamp",
    "Ingested_Log_Volume",
    "Baseline_Schema_Latency_ms",
    "Phase_ID",
]

# --- Governance risk model (shared with the React layer) -------------------
# risk_i = 100 * sensitivity * (W_LAT * lat_component + W_VOL * vol_component)
#   lat_component = clamp((latency * latency_factor - LAT_REF) / (LAT_MAX - LAT_REF), 0, 1)
#   vol_component = clamp((volume  * load_factor    - VOL_REF) / (VOL_MAX - VOL_REF), 0, 1)
# Composite risk = mean of risk_i over the most recent RECENT_WINDOW days.
# A composite > THRESHOLD raises the red-alert / XAI feed.
MODEL = {
    "LAT_REF": 0.55,
    "LAT_MAX": 2.40,
    "VOL_REF": 105.0,
    "VOL_MAX": 185.0,
    "W_LAT": 0.65,
    "W_VOL": 0.35,
    "THRESHOLD": 55.0,
    "RECENT_WINDOW": 10,
    # Default control-slider positions (Zone 3).
    "DEFAULT_LATENCY_FACTOR": 1.2,
    "DEFAULT_LOAD_FACTOR": 1.0,
    "DEFAULT_SENSITIVITY": 1.0,
}


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def load_raw() -> pd.DataFrame:
    """Stage 1: ingest the local mock log file."""
    if not CSV_PATH.exists():
        raise FileNotFoundError(
            f"{CSV_PATH.name} not found. Run `python data/generate_mock.py` first."
        )
    return pd.read_csv(CSV_PATH)


def normalize(raw: pd.DataFrame) -> pd.DataFrame:
    """Stage 2: enforce the unified governance schema."""
    missing = [c for c in REQUIRED_COLUMNS if c not in raw.columns]
    if missing:
        raise ValueError(f"CSV is missing required columns: {missing}")

    df = raw.copy()
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
    df["Ingested_Log_Volume"] = pd.to_numeric(df["Ingested_Log_Volume"], errors="coerce")
    df["Baseline_Schema_Latency_ms"] = pd.to_numeric(
        df["Baseline_Schema_Latency_ms"], errors="coerce"
    )
    df["Phase_ID"] = df["Phase_ID"].astype(str)
    df = df.dropna(subset=REQUIRED_COLUMNS).sort_values("Timestamp").reset_index(drop=True)
    return df


@st.cache_data(show_spinner=False)
def load_governance_data() -> pd.DataFrame:
    """Cached ingest + normalize. Re-runs only when the CSV changes."""
    return normalize(load_raw())


def point_risk(latency: float, volume: float, latency_factor: float,
               load_factor: float, sensitivity: float) -> float:
    lat_c = _clamp01((latency * latency_factor - MODEL["LAT_REF"]) /
                     (MODEL["LAT_MAX"] - MODEL["LAT_REF"]))
    vol_c = _clamp01((volume * load_factor - MODEL["VOL_REF"]) /
                     (MODEL["VOL_MAX"] - MODEL["VOL_REF"]))
    raw = 100.0 * sensitivity * (MODEL["W_LAT"] * lat_c + MODEL["W_VOL"] * vol_c)
    return max(0.0, min(100.0, raw))


def composite_risk(df: pd.DataFrame, latency_factor: float | None = None,
                   load_factor: float | None = None,
                   sensitivity: float | None = None) -> float:
    """Mean per-point risk over the most recent window (Python parity check)."""
    lf = MODEL["DEFAULT_LATENCY_FACTOR"] if latency_factor is None else latency_factor
    ld = MODEL["DEFAULT_LOAD_FACTOR"] if load_factor is None else load_factor
    sn = MODEL["DEFAULT_SENSITIVITY"] if sensitivity is None else sensitivity
    recent = df.tail(MODEL["RECENT_WINDOW"])
    risks = [
        point_risk(r.Baseline_Schema_Latency_ms, r.Ingested_Log_Volume, lf, ld, sn)
        for r in recent.itertuples()
    ]
    return round(sum(risks) / len(risks), 1) if risks else 0.0


def build_payload(df: pd.DataFrame) -> dict:
    """Serialize records + model constants for injection into the React app."""
    records = [
        {
            "t": ts.strftime("%Y-%m-%d"),
            "vol": round(float(vol), 1),
            "latency": round(float(lat), 3),
            "phase": str(phase),
        }
        for ts, vol, lat, phase in zip(
            df["Timestamp"], df["Ingested_Log_Volume"],
            df["Baseline_Schema_Latency_ms"], df["Phase_ID"],
        )
    ]
    return {
        "records": records,
        "model": MODEL,
        "meta": {
            "rows": len(records),
            "phases": sorted(df["Phase_ID"].unique().tolist()),
            "start": df["Timestamp"].min().strftime("%Y-%m-%d"),
            "end": df["Timestamp"].max().strftime("%Y-%m-%d"),
        },
    }
