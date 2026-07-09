"""Repeatability / noise floor.

Week 4's question: measure the same sample many times, how much does it drift?
The spread of repeats sets the noise floor -- a real difference between samples
has to be bigger than this to be believable.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .features import feature_columns, feature_table


def _is_phase_deg(name: str) -> bool:
    """A degree-valued phase feature (interval scale, can cross 0) -- not a frequency."""
    return name.startswith("phase") and "freq" not in name


def repeatability(master: pd.DataFrame, group_cols=("label", "concentration")) -> pd.DataFrame:
    """Per-feature spread across nominal repeats (same label+concentration).

    Reports mean, std, and an honest `spread`: for magnitude / frequency features
    (ratio scale, single sign) that's CV% ; for phase features (degrees, cross 0,
    where CV explodes near a zero mean) it's the absolute std in degrees. Small = trustworthy.
    """
    feats = feature_table(master)
    cols = feature_columns(feats)
    group_cols = [c for c in group_cols if c in feats.columns]
    rows = []
    for key, grp in feats.groupby(list(group_cols), sort=False):
        if len(grp) < 2:
            continue  # need repeats to talk about spread
        key = key if isinstance(key, tuple) else (key,)
        for col in cols:
            vals = grp[col].to_numpy(dtype=float)
            mean = np.nanmean(vals)
            std = np.nanstd(vals, ddof=1)
            if _is_phase_deg(col):
                spread, unit = std, "deg"
            else:
                spread = 100 * std / abs(mean) if mean else np.nan
                unit = "%"
            rows.append({
                **dict(zip(group_cols, key)),
                "feature": col, "n": len(grp),
                "mean": mean, "std": std,
                "spread": spread, "unit": unit,
            })
    return pd.DataFrame(rows)


def noise_summary(rep: pd.DataFrame) -> pd.DataFrame:
    """One-glance noise floor: median & max spread per feature, with its unit.

    Best-first by median spread. Magnitude rows read as CV%, phase rows as std in
    degrees -- so a phase feature near 0° no longer pollutes the table with a fake CV.
    """
    if rep.empty:
        return pd.DataFrame(columns=["feature", "unit", "median_spread", "max_spread"])
    out = (rep.groupby(["feature", "unit"])["spread"]
           .agg(median_spread="median", max_spread="max")
           .reset_index()
           .sort_values("median_spread"))
    return out


def separation(master: pd.DataFrame, feature: str, a: str, b: str,
               label_col: str = "label") -> dict:
    """Effect size between two classes on one feature: Cohen's d.

    d = |meanA - meanB| / pooled_sd, pooled_sd = sqrt(((nA-1)sA^2+(nB-1)sB^2)/(nA+nB-2)).
    In units of one within-class standard deviation, so >~2 means the classes sit
    more than two noise-widths apart -- cleanly distinguishable. Needs >=2 samples
    per class (spread is undefined otherwise) and returns NaN if not.
    """
    feats = feature_table(master)
    va = feats.loc[feats[label_col] == a, feature].to_numpy(dtype=float)
    vb = feats.loc[feats[label_col] == b, feature].to_numpy(dtype=float)
    na, nb = len(va), len(vb)
    if na < 2 or nb < 2:
        return {"feature": feature, "a": a, "b": b, "separation": np.nan}
    pooled = np.sqrt(((na - 1) * np.nanvar(va, ddof=1) +
                      (nb - 1) * np.nanvar(vb, ddof=1)) / (na + nb - 2))
    sep = abs(np.nanmean(va) - np.nanmean(vb)) / pooled if pooled else np.inf
    return {"feature": feature, "a": a, "b": b,
            "mean_a": np.nanmean(va), "mean_b": np.nanmean(vb), "separation": sep}
