"""Sweep quality control -- catch a bad measurement before it pollutes the data.

Week 4's rule: never save a garbage sweep as if it were good. These checks run the
data-side sanity that the firmware warning can't (shape across the whole sweep),
and they run identically on every file so QC is consistent for all five of us.

`validate_sweep` returns a list of Issue(severity, code, message). Empty list = clean.
Severities: "error" (do not trust), "warn" (look before using), nothing else.
"""

from __future__ import annotations

from collections import namedtuple

import numpy as np
import pandas as pd

Issue = namedtuple("Issue", "severity code message")

# Tunable thresholds. Loosen once real hardware noise is known.
MIN_POINTS = 5          # fewer points than this is not a usable sweep
FLAT_CV = 0.02          # magnitude CV below this = flat line (open/short/no sample)
NEAR_ZERO = 1e-9        # magnitude essentially zero = no contact / short
SPIKE_JUMP = 5.0        # point-to-point magnitude jump > this ×median = glitch


def validate_sweep(sweep: pd.DataFrame) -> list[Issue]:
    """Return QC issues for one sweep (long-form rows). Empty = passes."""
    issues: list[Issue] = []
    s = sweep.sort_values("frequency_hz")
    n = len(s)

    if n == 0:
        return [Issue("error", "empty", "sweep has no data rows")]
    if n < MIN_POINTS:
        issues.append(Issue("error", "too_few", f"only {n} points (< {MIN_POINTS})"))

    f = s["frequency_hz"].to_numpy(dtype=float)
    mag = s["magnitude"].to_numpy(dtype=float)
    ph = s["phase_deg"].to_numpy(dtype=float)

    if not np.all(np.isfinite(mag)) or not np.all(np.isfinite(ph)):
        issues.append(Issue("error", "nan", "NaN/inf in magnitude or phase"))

    if np.nanmedian(np.abs(mag)) < NEAR_ZERO:
        issues.append(Issue("error", "near_zero",
                            "magnitude ~0 everywhere (no contact / short?)"))

    # duplicate or non-increasing frequencies
    if len(np.unique(f)) < len(f):
        issues.append(Issue("warn", "dup_freq", "duplicate frequency points"))
    if np.any(np.diff(f) < 0):
        issues.append(Issue("warn", "unsorted", "frequencies not monotonically increasing"))

    # flat line: a real water sweep varies across frequency
    finite = mag[np.isfinite(mag)]
    if finite.size and np.mean(np.abs(finite)) > NEAR_ZERO:
        cv = np.std(finite) / np.mean(np.abs(finite))
        if cv < FLAT_CV:
            issues.append(Issue("warn", "flat",
                                f"magnitude nearly constant (CV={cv:.3f}); open circuit / no sample?"))

    # single-point spikes (loose connection glitch)
    if finite.size >= 3:
        med = np.median(np.abs(np.diff(finite)))
        if med > 0 and np.max(np.abs(np.diff(finite))) > SPIKE_JUMP * med * 4:
            issues.append(Issue("warn", "spike", "large single-point jump (glitch / loose wire?)"))

    return issues


def qc_folder(folder, gain_factor: float | None = None) -> pd.DataFrame:
    """Run QC over every sweep in a folder. One row per issue; empty frame = all clean."""
    from .io import ingest_folder  # local import avoids an import cycle

    master = ingest_folder(folder, gain_factor=gain_factor)
    rows = []
    for fname, grp in master.groupby("file", sort=False):
        for iss in validate_sweep(grp):
            rows.append({"file": fname, "severity": iss.severity,
                         "code": iss.code, "message": iss.message})
    return pd.DataFrame(rows, columns=["file", "severity", "code", "message"])
