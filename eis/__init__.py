"""EIS water-fingerprint pipeline (Conrad Challenge, software & data lane).

Public surface:
    ingest_folder, read_sweep    -- raw CSVs -> master table   (io)
    feature_table                -- master -> one row per sweep (features)
    plot_sweep, overlay          -- figures                    (plots)
    repeatability, noise_summary -- trustworthiness            (noise)
    clean_vs_dirty               -- optional tiny model        (model)
"""

from .io import ingest_folder, read_sweep, META_COLS
from .features import feature_table, feature_columns, sweep_features
from .plots import plot_sweep, overlay, feature_scatter
from .noise import repeatability, noise_summary, separation
from .model import clean_vs_dirty
from .qc import validate_sweep, qc_folder
from .report import build_report

__all__ = [
    "ingest_folder", "read_sweep", "META_COLS",
    "feature_table", "feature_columns", "sweep_features",
    "plot_sweep", "overlay", "feature_scatter",
    "repeatability", "noise_summary", "separation",
    "clean_vs_dirty",
    "validate_sweep", "qc_folder",
    "build_report",
]
