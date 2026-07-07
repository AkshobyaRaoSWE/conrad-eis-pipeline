"""Optional tiny classifier (Week 5's bonus peek).

Deliberately small: standardize features, logistic regression, leave-one-out CV
because the summer sample count is tiny. This is a sanity check that the features
carry class information -- the real fall model replaces it. No tuning, no leakage.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import LeaveOneOut, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .features import feature_columns


def clean_vs_dirty(feat_table: pd.DataFrame, dirty_labels=("yeast",),
                   clean_labels=("control", "tap")):
    """Binary clean-vs-contaminated check with leave-one-out CV.

    Returns (accuracy, confusion, detail_df). Tuned toward not missing dirty
    samples is a fall concern; here we just confirm the signal is learnable.
    """
    cols = feature_columns(feat_table)
    df = feat_table.copy()
    df = df[df["label"].isin(list(dirty_labels) + list(clean_labels))]
    y = df["label"].isin(dirty_labels).astype(int).to_numpy()  # 1 = dirty
    X = df[cols].to_numpy(dtype=float)

    if len(np.unique(y)) < 2:
        raise ValueError("Need both clean and dirty samples to classify.")

    clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))
    pred = cross_val_predict(clf, X, y, cv=LeaveOneOut())

    acc = float(np.mean(pred == y))
    tp = int(np.sum((pred == 1) & (y == 1)))
    fn = int(np.sum((pred == 0) & (y == 1)))
    fp = int(np.sum((pred == 1) & (y == 0)))
    tn = int(np.sum((pred == 0) & (y == 0)))
    detail = df[["sample_id", "label"]].copy()
    detail["true_dirty"] = y
    detail["pred_dirty"] = pred
    confusion = {"tp": tp, "fn": fn, "fp": fp, "tn": tn}
    return acc, confusion, detail
