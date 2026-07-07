"""Plots: single sweep (sanity check) and overlays (do samples separate?).

Matplotlib only, headless-safe (Agg). Dark, minimal styling so figures drop
straight into the fall video/website without rework.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# consistent color per class across every figure
CLASS_COLORS = {
    "control": "#6ee7ff",
    "tap": "#a3e635",
    "salt": "#fbbf24",
    "yeast": "#f472b6",
}
_FALLBACK = ["#818cf8", "#f87171", "#34d399", "#e879f9", "#facc15"]


def _style():
    plt.rcParams.update({
        "figure.facecolor": "#0b0d10",
        "axes.facecolor": "#0b0d10",
        "savefig.facecolor": "#0b0d10",
        "text.color": "#e6e8ea",
        "axes.labelcolor": "#e6e8ea",
        "xtick.color": "#9aa0a6",
        "ytick.color": "#9aa0a6",
        "axes.edgecolor": "#2a2e33",
        "grid.color": "#1a1d21",
        "font.size": 10,
    })


def _color(label: str, i: int) -> str:
    return CLASS_COLORS.get(str(label), _FALLBACK[i % len(_FALLBACK)])


def plot_sweep(sweep, out_path, title: str | None = None):
    """Magnitude and phase vs frequency for one sweep. The 'does it look sane' plot."""
    _style()
    s = sweep.sort_values("frequency_hz")
    f = s["frequency_hz"]
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(7, 6), sharex=True)
    ax1.semilogx(f, s["magnitude"], color="#6ee7ff", lw=1.6)
    ax1.set_ylabel("|magnitude|")
    ax1.grid(True, which="both", lw=0.5)
    ax2.semilogx(f, s["phase_deg"], color="#f472b6", lw=1.6)
    ax2.set_ylabel("phase (deg)")
    ax2.set_xlabel("frequency (Hz)")
    ax2.grid(True, which="both", lw=0.5)
    fig.suptitle(title or str(s["sample_id"].iloc[0]))
    fig.tight_layout()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=140)
    plt.close(fig)
    return out_path


def overlay(master, out_path, value: str = "magnitude", by: str = "label"):
    """Overlay every sweep colored by class. This is the eyeball separation test."""
    _style()
    fig, ax = plt.subplots(figsize=(8, 5))
    seen = {}
    for i, (sid, grp) in enumerate(master.groupby("sample_id", sort=False)):
        g = grp.sort_values("frequency_hz")
        cls = str(g[by].iloc[0])
        color = _color(cls, i)
        ax.semilogx(g["frequency_hz"], g[value], color=color, lw=1.3, alpha=0.85,
                    label=cls if cls not in seen else None)
        seen[cls] = True
    ax.set_xlabel("frequency (Hz)")
    ax.set_ylabel(value)
    ax.set_title(f"{value} overlay by {by}")
    ax.grid(True, which="both", lw=0.5)
    ax.legend(frameon=False)
    fig.tight_layout()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=140)
    plt.close(fig)
    return out_path


def feature_scatter(feat_table, out_path, x: str, y: str, by: str = "label"):
    """2-D feature scatter -- do the classes form separate clouds?"""
    _style()
    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    for i, (cls, grp) in enumerate(feat_table.groupby(by, sort=False)):
        ax.scatter(grp[x], grp[y], s=70, color=_color(str(cls), i),
                   edgecolor="#0b0d10", lw=0.5, label=str(cls))
    ax.set_xlabel(x)
    ax.set_ylabel(y)
    ax.set_title(f"{y} vs {x}")
    ax.grid(True, lw=0.5)
    ax.legend(frameon=False)
    fig.tight_layout()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=140)
    plt.close(fig)
    return out_path
