"""Synthetic EIS sweeps so the whole pipeline is testable before hardware exists.

Physics stand-in: a water sample is a Randles-style cell -- solution resistance
Rs (set by ions / salt) in series with a charge-transfer resistance Rct in
parallel with a double-layer capacitance C (both shifted by organic / microbial
load). Impedance:

    Z(w) = Rs + Rct / (1 + j*w*Rct*C)

Different sample types get different (Rs, Rct, C), so their magnitude/phase
sweeps genuinely separate -- which is exactly what the real sensor should show.
This is a placeholder to exercise ingest/features/plots/model, NOT a claim about
real water. It is deleted the moment real CSVs exist.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

# Sweep grid the firmware is expected to use (log-spaced, AD5933 range).
DEFAULT_FREQS = np.round(np.logspace(np.log10(1e3), np.log10(1e5), 40)).astype(int)

# (Rs ohms, Rct ohms, C farads) per sample class. Tuned so classes separate but
# overlap a little -- realistic, not trivially easy.
SAMPLE_TYPES = {
    "control": (1200, 9000, 1.5e-8),   # clean distilled-ish
    "tap":     (700,  7000, 1.8e-8),   # more ions, lower Rs
    "salt":    (250,  6000, 2.0e-8),   # ionic, low Rs
    "yeast":   (1000, 3500, 4.5e-8),   # microbial load drops Rct, raises C
}


def _rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)


def sweep(sample_type: str, freqs=None, scale: float = 1.0, seed: int = 0):
    """Return (freqs, real, imag) for one noisy sweep of a sample type.

    `scale` nudges Rct/C to fake a concentration series (higher = stronger load).
    """
    if freqs is None:
        freqs = DEFAULT_FREQS
    rng = _rng(seed)
    rs, rct, c = SAMPLE_TYPES[sample_type]
    # concentration effect: more load -> lower Rct, higher C
    rct = rct / scale
    c = c * scale
    # small per-sample component tolerance
    rs *= rng.normal(1.0, 0.03)
    rct *= rng.normal(1.0, 0.05)
    c *= rng.normal(1.0, 0.05)

    w = 2 * np.pi * freqs
    z = rs + rct / (1 + 1j * w * rct * c)
    real = np.real(z)
    imag = np.imag(z)
    # measurement noise (~1.5% of local magnitude) so repeatability tests have work to do
    mag = np.hypot(real, imag)
    real = real + rng.normal(0, 0.015 * mag)
    imag = imag + rng.normal(0, 0.015 * mag)
    return freqs, real, imag


_CONC_SCALE = {"na": 1.0, "low": 0.6, "med": 1.0, "high": 1.8, "strong": 2.4}


def write_dataset(out_dir, repeats: int = 3, base_seed: int = 1):
    """Generate a labeled folder of sweep CSVs mimicking a summer proof-of-concept run.

    Produces controls, tap, salt, and a yeast concentration series, `repeats` each,
    named by the SWEEP_FORMAT convention so ingest auto-labels them.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    plan = [
        ("control", "na"),
        ("tap", "na"),
        ("salt", "na"),
        ("yeast", "low"),
        ("yeast", "med"),
        ("yeast", "high"),
    ]
    seed = base_seed
    written = []
    for label, conc in plan:
        for rep in range(1, repeats + 1):
            seed += 1
            f, re_, im_ = sweep(label, scale=_CONC_SCALE[conc], seed=seed)
            fname = f"{label}_{conc}_{rep:02d}.csv"
            path = out_dir / fname
            with path.open("w") as fh:
                fh.write(f"# sample_id: {label}_{conc}_{rep:02d}\n")
                fh.write(f"# additives: {'salt' if label=='salt' else 'none'}\n")
                fh.write("frequency_hz,real,imag\n")
                for a, b, c_ in zip(f, re_, im_):
                    fh.write(f"{int(a)},{b:.2f},{c_:.2f}\n")
            written.append(path)
    return written
