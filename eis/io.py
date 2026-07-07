"""Read AD5933 sweep CSVs and build one master table.

See ../SWEEP_FORMAT.md for the file contract. This module is the only place that
knows how a raw file turns into labeled, derived-column rows, so the rest of the
pipeline never touches parsing.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

# Metadata columns every sweep carries, in order.
META_COLS = [
    "sample_id",
    "file",
    "label",
    "concentration",
    "repeat",
    "additives",
    "temperature_c",
    "timestamp",
]


def _parse_header(path: Path) -> dict:
    """Pull `# key: value` lines from the top of a file into a dict."""
    meta = {}
    with path.open() as fh:
        for line in fh:
            s = line.strip()
            if not s:
                continue
            if not s.startswith("#"):
                break  # first data/column line ends the header
            body = s.lstrip("#").strip()
            if ":" in body:
                k, v = body.split(":", 1)
                meta[k.strip().lower()] = v.strip()
    return meta


def _parse_filename(path: Path) -> dict:
    """Label from `<label>_<concentration>_<repeat>[_...].csv`. Lenient."""
    stem = path.stem
    parts = stem.split("_")
    meta = {"sample_id": stem}
    if len(parts) >= 1 and parts[0]:
        meta["label"] = parts[0]
    if len(parts) >= 2:
        meta["concentration"] = parts[1]
    if len(parts) >= 3:
        m = re.search(r"\d+", parts[2])
        if m:
            meta["repeat"] = int(m.group())
    return meta


def _derive(df: pd.DataFrame, gain_factor: float | None) -> pd.DataFrame:
    """Add magnitude / phase / impedance columns from real & imag if absent."""
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    if "magnitude" not in df.columns:
        df["magnitude"] = np.hypot(df["real"], df["imag"])
    if "phase_deg" not in df.columns:
        df["phase_deg"] = np.degrees(np.arctan2(df["imag"], df["real"]))
    if "impedance_ohm" not in df.columns and gain_factor:
        # |Z| = 1 / (gain_factor * magnitude); guard against zero magnitude.
        mag = df["magnitude"].replace(0, np.nan)
        df["impedance_ohm"] = 1.0 / (gain_factor * mag)
    return df.sort_values("frequency_hz").reset_index(drop=True)


def read_sweep(path, manifest: dict | None = None, gain_factor: float | None = None) -> pd.DataFrame:
    """Read one sweep CSV into a long DataFrame with metadata columns filled.

    Precedence for metadata: in-file `#` header > manifest row > filename. The
    closest source to the actual measurement wins.
    """
    path = Path(path)
    meta = {"sample_id": path.stem, "file": path.name}
    meta.update(_parse_filename(path))
    if manifest:
        meta.update({k: v for k, v in manifest.items() if v not in (None, "")})
    header = _parse_header(path)
    if "gain_factor" in header:
        gain_factor = float(header.pop("gain_factor"))
    meta.update(header)  # header wins

    data = pd.read_csv(path, comment="#")
    data = _derive(data, gain_factor)

    for col in META_COLS:
        data[col] = meta.get(col, "")
    data["file"] = path.name
    if not data["sample_id"].iloc[0]:
        data["sample_id"] = path.stem
    return data


def _load_manifest(folder: Path) -> dict:
    """Read data/raw/manifest.csv into {filename: {col: val}} if present."""
    mpath = folder / "manifest.csv"
    if not mpath.exists():
        return {}
    m = pd.read_csv(mpath).fillna("")
    out = {}
    for _, row in m.iterrows():
        d = row.to_dict()
        fn = d.pop("filename", None)
        if fn:
            out[str(fn).strip()] = d
    return out


def ingest_folder(folder, gain_factor: float | None = None) -> pd.DataFrame:
    """Load every sweep CSV in a folder into one long master table.

    This is the auto-ingest loop: drop any new labeled CSV into the folder and it
    joins the table on the next run. `manifest.csv` is skipped as a data file.
    """
    folder = Path(folder)
    manifest = _load_manifest(folder)
    frames = []
    for path in sorted(folder.glob("*.csv")):
        if path.name == "manifest.csv":
            continue
        frames.append(read_sweep(path, manifest.get(path.name), gain_factor))
    if not frames:
        raise FileNotFoundError(f"No sweep CSVs found in {folder}")
    table = pd.concat(frames, ignore_index=True)
    return table
