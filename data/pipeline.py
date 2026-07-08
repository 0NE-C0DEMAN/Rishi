"""Data ingestion + normalization for the governance console (TRD Task 2).

This is the deterministic Pandas pipeline the TRD asks for:

  * Stage 1 (Ingestion)     -> ``load_raw`` reads the local mock CSV
                               (``data/mock_logistics_data.csv``).
  * Stage 2 (Normalization) -> ``normalize`` enforces the tracking schema
                               (Timestamp, Ingested_Log_Volume,
                               Baseline_Schema_Latency_ms, Phase_ID).

``load_governance_data`` caches the result with ``@st.cache_data`` so the CSV
is parsed once per session (re-parsed only when the file changes).
``build_payload`` serialises the normalized records for injection into the
embedded Meridian console; the in-browser governance model scores risk from
these records client-side so the sliders respond instantly.
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


def load_raw() -> pd.DataFrame:
    """Stage 1: ingest the local mock log export."""
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
    return df.dropna(subset=REQUIRED_COLUMNS).sort_values("Timestamp").reset_index(drop=True)


@st.cache_data(show_spinner=False)
def load_governance_data() -> pd.DataFrame:
    """Cached ingest + normalize. Re-runs only when the CSV changes."""
    return normalize(load_raw())


def build_payload(df: pd.DataFrame) -> dict:
    """Serialize the normalized records for the embedded console."""
    records = [
        {
            "t": ts.strftime("%Y-%m-%d"),
            "vol": round(float(vol), 1),
            "latency": round(float(lat), 3),
            "phase": str(phase),
        }
        for ts, vol, lat, phase in zip(
            df["Timestamp"],
            df["Ingested_Log_Volume"],
            df["Baseline_Schema_Latency_ms"],
            df["Phase_ID"],
        )
    ]
    return {
        "records": records,
        "meta": {
            "rows": len(records),
            "phases": sorted(df["Phase_ID"].unique().tolist()),
            "start": df["Timestamp"].min().strftime("%Y-%m-%d"),
            "end": df["Timestamp"].max().strftime("%Y-%m-%d"),
            "source": CSV_PATH.name,
        },
    }
