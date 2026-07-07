"""Repeatability / noise floor.

Week 4's question: measure the same sample many times, how much does it drift?
The spread of repeats sets the noise floor -- a real difference between samples
has to be bigger than this to be believable.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .features import feature_columns, feature_table


def repeatability(master: pd.DataFrame, group_cols=("label", "concentration")) -> pd.DataFrame:
    """Coefficient of variation per feature, per repeated group.

    Groups sweeps that share label+concentration (i.e. nominal repeats of the
    same sample) and reports mean / std / CV% for each feature. Small CV = trustworthy.
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
            cv = 100 * std / abs(mean) if mean else np.nan
            rows.append({
                **dict(zip(group_cols, key)),
                "feature": col,
                "n": len(grp),
                "mean": mean,
                "std": std,
                "cv_pct": cv,
            })
    return pd.DataFrame(rows)


def noise_summary(rep: pd.DataFrame) -> pd.DataFrame:
    """Median CV% per feature across all groups -- the one-glance noise floor."""
    if rep.empty:
        return pd.DataFrame(columns=["feature", "median_cv_pct", "max_cv_pct"])
    out = (rep.groupby("feature")["cv_pct"]
           .agg(median_cv_pct="median", max_cv_pct="max")
           .reset_index()
           .sort_values("median_cv_pct"))
    return out


def separation(master: pd.DataFrame, feature: str, a: str, b: str,
               label_col: str = "label") -> dict:
    """How many noise-widths apart are two classes on one feature?

    Returns a z-like separation: |meanA - meanB| / pooled_std. >~2 means the
    classes are cleanly distinguishable on that feature above the noise.
    """
    feats = feature_table(master)
    va = feats.loc[feats[label_col] == a, feature].to_numpy(dtype=float)
    vb = feats.loc[feats[label_col] == b, feature].to_numpy(dtype=float)
    if len(va) < 1 or len(vb) < 1:
        return {"feature": feature, "a": a, "b": b, "separation": np.nan}
    pooled = np.sqrt((np.nanvar(va, ddof=1) if len(va) > 1 else 0) +
                     (np.nanvar(vb, ddof=1) if len(vb) > 1 else 0))
    sep = abs(np.nanmean(va) - np.nanmean(vb)) / pooled if pooled else np.inf
    return {"feature": feature, "a": a, "b": b,
            "mean_a": np.nanmean(va), "mean_b": np.nanmean(vb), "separation": sep}
