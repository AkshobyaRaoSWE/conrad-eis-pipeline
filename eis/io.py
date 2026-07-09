"""Read AD5933 sweep CSVs and build one master table.

See ../SWEEP_FORMAT.md for the file contract. This module is the only place that
knows how a raw file turns into labeled, derived-column rows, so the rest of the
pipeline never touches parsing.
"""

from __future__ import annotations

import re
import sys
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
    # utf-8-sig so a leading BOM doesn't hide the first '#' header line.
    with path.open(encoding="utf-8-sig") as fh:
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
    """Add magnitude / phase / impedance columns from real & imag if absent.

    Requires either (real & imag) or the already-computed column. Missing inputs
    raise a clear ValueError instead of a cryptic KeyError deep in the math.
    """
    df = df.copy()
    df.columns = [c.strip().lower() for c in df.columns]
    if "frequency_hz" not in df.columns:
        raise ValueError("missing required column 'frequency_hz'")
    have_ri = {"real", "imag"} <= set(df.columns)
    if "magnitude" not in df.columns:
        if not have_ri:
            raise ValueError("need 'real' & 'imag' columns to derive 'magnitude' "
                             "(or provide a 'magnitude' column)")
        df["magnitude"] = np.hypot(df["real"], df["imag"])
    if "phase_deg" not in df.columns:
        if not have_ri:
            raise ValueError("need 'real' & 'imag' columns to derive 'phase_deg' "
                             "(or provide a 'phase_deg' column)")
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

    # Normalize repeat to a single type regardless of source (filename/manifest give
    # int, a header gives str) so groupby/filter never splits identical repeats.
    if str(meta.get("repeat", "")).strip().isdigit():
        meta["repeat"] = int(meta["repeat"])

    data = pd.read_csv(path, comment="#", encoding="utf-8-sig")
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
    frames, skipped = [], []
    for path in sorted(folder.glob("*.csv")):
        if path.name == "manifest.csv":
            continue
        try:
            frames.append(read_sweep(path, manifest.get(path.name), gain_factor))
        except Exception as exc:
            # One malformed file must not sink the whole batch (shared folder,
            # five people). Skip it, but say so loudly so it's never lost silently.
            skipped.append((path.name, str(exc)))
    for name, why in skipped:
        print(f"[ingest] skipped {name}: {why}", file=sys.stderr)
    if not frames:
        if skipped:
            raise ValueError(f"No readable sweeps in {folder}; "
                             f"{len(skipped)} file(s) failed to parse")
        raise FileNotFoundError(f"No sweep CSVs found in {folder}")
    return pd.concat(frames, ignore_index=True)
