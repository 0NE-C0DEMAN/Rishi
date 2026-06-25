"""Deterministic generator for the mock governance dataset.

Produces ``mock_logistics_data.csv`` with the columns named in the TRD:
    Timestamp, Ingested_Log_Volume, Baseline_Schema_Latency_ms, Phase_ID

The data is seeded so every run is identical (no random drift between
milestones). Latency drifts upward across later phases so that raising the
control sliders in the dashboard pushes composite risk across the 55% line —
which is what makes the interactive demo legible.

Run:  python data/generate_mock.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

SEED = 7
N_DAYS = 75
START = "2026-03-01"
PHASES = ["P-01 Discovery", "P-02 Design", "P-03 Build", "P-04 Integrate", "P-05 Stabilize"]


def build_frame() -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    dates = pd.date_range(start=START, periods=N_DAYS, freq="D")

    # Phase index 0..4 spread evenly across the timeline.
    phase_idx = np.minimum((np.arange(N_DAYS) // (N_DAYS // len(PHASES))), len(PHASES) - 1)

    # Latency drifts up by phase (0.55ms -> ~1.35ms) with daily noise.
    base_latency = 0.55 + phase_idx * 0.20
    latency = base_latency + rng.normal(0, 0.06, N_DAYS)
    latency = np.clip(latency, 0.2, None).round(3)

    # Volume rises slowly with phase, with noise.
    base_volume = 96 + phase_idx * 6
    volume = base_volume + rng.normal(0, 12, N_DAYS)
    volume = np.clip(volume, 40, None).round(1)

    return pd.DataFrame(
        {
            "Timestamp": dates.strftime("%Y-%m-%d"),
            "Ingested_Log_Volume": volume,
            "Baseline_Schema_Latency_ms": latency,
            "Phase_ID": [PHASES[i] for i in phase_idx],
        }
    )


def main() -> None:
    out = Path(__file__).resolve().parent / "mock_logistics_data.csv"
    df = build_frame()
    df.to_csv(out, index=False)
    print(f"Wrote {len(df)} rows -> {out}")


if __name__ == "__main__":
    main()
