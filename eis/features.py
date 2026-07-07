"""Turn each sweep into a small fixed feature vector for comparison / modeling.

Features are the ones the plan calls out: magnitude & phase sampled at a few key
frequencies, plus a couple of whole-sweep summaries (phase peak, where it peaks).
One row per sweep. Kept deliberately small and interpretable -- the fall model
can expand this, but these already separate the classes.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .io import META_COLS

# Frequencies (Hz) to sample features at. Low / mid / high across the sweep;
# nearest available point is used so this works on any grid.
KEY_FREQS = [1_000, 5_000, 20_000, 50_000, 100_000]


def _nearest(freqs: np.ndarray, target: float) -> int:
    return int(np.argmin(np.abs(freqs - target)))


def sweep_features(sweep: pd.DataFrame) -> dict:
    """Feature dict for a single sweep (long-form rows for one sample_id)."""
    s = sweep.sort_values("frequency_hz")
    f = s["frequency_hz"].to_numpy()
    mag = s["magnitude"].to_numpy()
    ph = s["phase_deg"].to_numpy()

    feats = {}
    for tf in KEY_FREQS:
        i = _nearest(f, tf)
        feats[f"mag_{tf}"] = mag[i]
        feats[f"phase_{tf}"] = ph[i]

    # whole-sweep summaries
    feats["mag_min"] = mag.min()
    feats["mag_max"] = mag.max()
    feats["mag_ratio"] = mag.max() / mag.min() if mag.min() else np.nan
    ipk = int(np.argmin(ph))  # most negative phase = strongest capacitive dip
    feats["phase_peak"] = ph[ipk]
    feats["phase_peak_freq"] = f[ipk]
    return feats


def feature_table(master: pd.DataFrame) -> pd.DataFrame:
    """One row of features per sweep, carrying metadata columns along."""
    rows = []
    # Group by file, not sample_id: one file == one sweep and filenames are unique,
    # so two sweeps that happen to share a sample_id are never collapsed together.
    for fname, grp in master.groupby("file", sort=False):
        meta = {c: grp[c].iloc[0] for c in META_COLS if c in grp.columns}
        meta.update(sweep_features(grp))
        rows.append(meta)
    return pd.DataFrame(rows)


def feature_columns(table: pd.DataFrame) -> list[str]:
    """Names of the numeric feature columns (everything that isn't metadata)."""
    return [c for c in table.columns if c not in META_COLS]
