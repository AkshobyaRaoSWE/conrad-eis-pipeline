"""Regression tests for the EIS pipeline. Run: pytest

Covers the format contract, metadata precedence, derived columns, QC, features,
noise, model, and report -- including the edge cases that broke earlier (empty
files, id collisions, bad columns). No hardware, no network.
"""

import numpy as np
import pandas as pd
import pytest

import eis
from eis import synth


def write(folder, name, text):
    p = folder / name
    p.write_text(text)
    return p


# ---------- io: reading & derived columns ----------

def test_derived_magnitude_phase(tmp_path):
    write(tmp_path, "control_na_01.csv", "frequency_hz,real,imag\n1000,3,4\n2000,6,8\n")
    s = eis.read_sweep(tmp_path / "control_na_01.csv")
    assert abs(s["magnitude"].iloc[0] - 5) < 1e-9          # hypot(3,4)
    assert abs(s["phase_deg"].iloc[0] - np.degrees(np.arctan2(4, 3))) < 1e-9


def test_precomputed_columns_respected(tmp_path):
    write(tmp_path, "x_na_01.csv",
          "frequency_hz,real,imag,magnitude,phase_deg\n1000,3,4,999,12\n2000,6,8,999,12\n")
    s = eis.read_sweep(tmp_path / "x_na_01.csv")
    assert s["magnitude"].iloc[0] == 999 and s["phase_deg"].iloc[0] == 12


def test_gain_factor_to_ohms_and_zero_guard(tmp_path):
    write(tmp_path, "z_na_01.csv", "frequency_hz,real,imag\n1000,0,0\n2000,3,4\n")
    s = eis.read_sweep(tmp_path / "z_na_01.csv", gain_factor=1e-9)
    assert np.isnan(s["impedance_ohm"].iloc[0])            # no div-by-zero
    assert np.isfinite(s["impedance_ohm"].iloc[1])


def test_missing_columns_raise(tmp_path):
    write(tmp_path, "bad.csv", "frequency_hz,foo\n1000,5\n")
    with pytest.raises(ValueError, match="real.*imag"):     # clear error, not cryptic KeyError
        eis.read_sweep(tmp_path / "bad.csv")


def test_column_whitespace_and_case(tmp_path):
    write(tmp_path, "ws_na_01.csv", "Frequency_Hz, REAL , Imag\n1000,3,4\n2000,6,8\n")
    s = eis.read_sweep(tmp_path / "ws_na_01.csv")
    assert abs(s["magnitude"].iloc[0] - 5) < 1e-9


# ---------- metadata precedence: header > manifest > filename ----------

def test_filename_labeling(tmp_path):
    write(tmp_path, "yeast_med_03.csv", "frequency_hz,real,imag\n1000,3,4\n2000,6,8\n")
    s = eis.read_sweep(tmp_path / "yeast_med_03.csv")
    assert s["label"].iloc[0] == "yeast"
    assert s["concentration"].iloc[0] == "med"
    assert int(s["repeat"].iloc[0]) == 3


def test_header_overrides_filename(tmp_path):
    write(tmp_path, "tap_na_01.csv", "# label: control\nfrequency_hz,real,imag\n1000,3,4\n2000,6,8\n")
    s = eis.read_sweep(tmp_path / "tap_na_01.csv")
    assert s["label"].iloc[0] == "control"


def test_manifest_overrides_filename(tmp_path):
    write(tmp_path, "scan01.csv", "frequency_hz,real,imag\n1000,3,4\n2000,6,8\n")
    write(tmp_path, "manifest.csv",
          "filename,label,concentration,repeat,additives,notes\nscan01.csv,yeast,med,2,salt,x\n")
    m = eis.ingest_folder(tmp_path)
    r = m[m.file == "scan01.csv"].iloc[0]
    assert r["label"] == "yeast" and r["additives"] == "salt"


def test_manifest_ghost_file_ignored(tmp_path):
    write(tmp_path, "a_na_01.csv", "frequency_hz,real,imag\n1000,3,4\n2000,6,8\n")
    write(tmp_path, "manifest.csv",
          "filename,label,concentration,repeat,additives,notes\nGHOST.csv,x,y,1,z,q\n")
    m = eis.ingest_folder(tmp_path)
    assert "manifest.csv" not in set(m["file"]) and "GHOST.csv" not in set(m["file"])


def test_empty_folder_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        eis.ingest_folder(tmp_path)


def test_one_bad_file_does_not_sink_batch(tmp_path):
    synth.write_dataset(tmp_path, repeats=2)                # 12 good sweeps
    (tmp_path / "oops_na_01.csv").write_text("frequency_hz,magnitude\n1000,500\n2000,400\n")
    m = eis.ingest_folder(tmp_path)                         # must not raise
    assert m["file"].nunique() == 12                        # good ones survive
    assert "oops_na_01.csv" not in set(m["file"])           # bad one skipped


def test_magnitude_only_gives_clear_error(tmp_path):
    write(tmp_path, "m.csv", "frequency_hz,magnitude\n1000,500\n2000,400\n")
    with pytest.raises(ValueError, match="real.*imag"):
        eis.read_sweep(tmp_path / "m.csv")


def test_magnitude_and_phase_only_ok(tmp_path):
    write(tmp_path, "mp_na_01.csv", "frequency_hz,magnitude,phase_deg\n1000,500,-30\n2000,400,-20\n")
    s = eis.read_sweep(tmp_path / "mp_na_01.csv")
    assert s["magnitude"].iloc[0] == 500 and s["phase_deg"].iloc[0] == -30


def test_all_bad_folder_raises_value_error(tmp_path):
    write(tmp_path, "x.csv", "frequency_hz,magnitude\n1000,500\n")
    with pytest.raises(ValueError):
        eis.ingest_folder(tmp_path)


def test_impedance_numeric_exact(tmp_path):
    write(tmp_path, "a_na_01.csv", "frequency_hz,real,imag\n1000,3,-4\n2000,3,-4\n")
    s = eis.read_sweep(tmp_path / "a_na_01.csv", gain_factor=2e-3)
    assert abs(s["magnitude"].iloc[0] - 5.0) < 1e-12
    assert abs(s["phase_deg"].iloc[0] - (-53.13010235)) < 1e-6
    assert abs(s["impedance_ohm"].iloc[0] - 100.0) < 1e-9   # 1/(2e-3*5)


def test_bom_column_resolves(tmp_path):
    (tmp_path / "b_na_01.csv").write_bytes("﻿frequency_hz,real,imag\n1000,3,4\n2000,6,8\n".encode())
    s = eis.read_sweep(tmp_path / "b_na_01.csv")
    assert abs(s["magnitude"].iloc[0] - 5.0) < 1e-12         # column survived BOM


# ---------- the bug that bit us: id collision must not merge sweeps ----------

def test_duplicate_sample_id_not_merged(tmp_path):
    write(tmp_path, "f1.csv", "# sample_id: dup\nfrequency_hz,real,imag\n1000,3,4\n2000,6,8\n")
    write(tmp_path, "f2.csv", "# sample_id: dup\nfrequency_hz,real,imag\n1000,30,40\n2000,60,80\n")
    m = eis.ingest_folder(tmp_path)
    assert len(eis.feature_table(m)) == 2                  # two files -> two rows


# ---------- features ----------

def test_feature_table_one_row_per_sweep(tmp_path):
    synth.write_dataset(tmp_path, repeats=2)
    m = eis.ingest_folder(tmp_path)
    ft = eis.feature_table(m)
    assert len(ft) == m["file"].nunique()
    for col in ("mag_1000", "phase_peak", "phase_peak_freq"):
        assert col in ft.columns


def test_short_sweep_features_are_nan_not_extrapolated(tmp_path):
    # 2-point sweep near 1-2 kHz: 100 kHz is out of range -> NaN, not a false value
    write(tmp_path, "s_na_01.csv", "frequency_hz,real,imag\n1000,3,4\n2000,6,8\n")
    ft = eis.feature_table(eis.ingest_folder(tmp_path))
    assert np.isnan(ft["mag_100000"].iloc[0])              # no silent extrapolation
    assert np.isfinite(ft["mag_1000"].iloc[0])             # in-range feature still real


# ---------- QC ----------

def test_qc_flags_flat_sweep(tmp_path):
    # constant magnitude -> flat / open-circuit warning
    rows = "\n".join(f"{f},100,0" for f in range(1000, 6000, 1000))
    write(tmp_path, "flat_na_01.csv", f"frequency_hz,real,imag\n{rows}\n")
    issues = eis.validate_sweep(eis.read_sweep(tmp_path / "flat_na_01.csv"))
    assert any(i.code == "flat" for i in issues)


def test_qc_clean_sweep_passes(tmp_path):
    synth.write_dataset(tmp_path, repeats=1)
    qc = eis.qc_folder(tmp_path)
    # synthetic sweeps are well-formed; no errors expected
    assert (qc["severity"] == "error").sum() == 0 if not qc.empty else True


# ---------- noise ----------

def test_repeatability_and_separation(tmp_path):
    synth.write_dataset(tmp_path, repeats=3)
    m = eis.ingest_folder(tmp_path)
    rep = eis.repeatability(m)
    assert not rep.empty and (rep["spread"].dropna() >= 0).all()
    # phase features carry a degree unit, magnitude features a percent unit
    assert set(rep["unit"]) <= {"%", "deg"}
    sep = eis.separation(m, "mag_20000", "control", "yeast")
    assert sep["separation"] >= 0


def test_separation_cohens_d_matches_manual(tmp_path):
    # ground-truth Cohen's d on a tiny hand-built table
    synth.write_dataset(tmp_path, repeats=3)
    m = eis.ingest_folder(tmp_path)
    ft = eis.feature_table(m)
    a = ft.loc[ft.label == "control", "mag_20000"].to_numpy(float)
    b = ft.loc[ft.label == "salt", "mag_20000"].to_numpy(float)
    na, nb = len(a), len(b)
    pooled = np.sqrt(((na-1)*a.var(ddof=1) + (nb-1)*b.var(ddof=1)) / (na+nb-2))
    want = abs(a.mean() - b.mean()) / pooled
    got = eis.separation(m, "mag_20000", "control", "salt")["separation"]
    assert abs(got - want) < 1e-9


def test_separation_nan_when_class_has_one_sample(tmp_path):
    synth.write_dataset(tmp_path, repeats=1)               # 1 control, 1 salt, ...
    m = eis.ingest_folder(tmp_path)
    sep = eis.separation(m, "mag_20000", "control", "salt")
    assert np.isnan(sep["separation"])                     # undefined spread -> NaN, not inf


# ---------- model ----------

def test_model_learns_synthetic(tmp_path):
    synth.write_dataset(tmp_path, repeats=3)
    ft = eis.feature_table(eis.ingest_folder(tmp_path))
    acc, conf, _ = eis.clean_vs_dirty(ft)
    assert acc >= 0.8                                       # signal is learnable
    assert conf["fn"] == 0                                  # no missed contamination


def test_model_single_class_raises(tmp_path):
    for i in (1, 2):
        write(tmp_path, f"control_na_0{i}.csv", "frequency_hz,real,imag\n1000,3,4\n2000,6,8\n")
    ft = eis.feature_table(eis.ingest_folder(tmp_path))
    with pytest.raises(ValueError):
        eis.clean_vs_dirty(ft)


# ---------- report ----------

def test_bom_header_still_labels(tmp_path):
    # BOM before the first '#' must not hide the authoritative header
    (tmp_path / "x_na_01.csv").write_bytes(
        "﻿# label: yeast\n# gain_factor: 2e-3\nfrequency_hz,real,imag\n1000,3,4\n2000,6,8\n".encode())
    s = eis.read_sweep(tmp_path / "x_na_01.csv")
    assert s["label"].iloc[0] == "yeast"                    # header won, not filename 'x'
    assert "impedance_ohm" in s.columns                     # gain_factor from header applied


def test_repeat_type_consistent_across_sources(tmp_path):
    write(tmp_path, "yeast_med_02.csv", "frequency_hz,real,imag\n1000,3,4\n2000,6,8\n")
    write(tmp_path, "hdr.csv", "# label: yeast\n# repeat: 2\nfrequency_hz,real,imag\n1000,3,4\n2000,6,8\n")
    m = eis.ingest_folder(tmp_path)
    reps = m.groupby("file")["repeat"].first()
    assert all(isinstance(v, (int, np.integer)) for v in reps)   # int from both sources
    assert (reps == 2).all()


def test_qc_spike_detects_glitch_not_steep_sweep(tmp_path):
    from eis.qc import validate_sweep
    # steep-but-clean monotone sweep -> NO spike flag
    synth.write_dataset(tmp_path, repeats=1)
    clean = eis.read_sweep(next(tmp_path.glob("control_*.csv")))
    assert not any(i.code == "spike" for i in validate_sweep(clean))
    # inject a single-point glitch -> flagged
    glitch = clean.copy()
    glitch.loc[glitch.index[5], "magnitude"] *= 8
    assert any(i.code == "spike" for i in validate_sweep(glitch))


def test_capture_parse_stream_end_token():
    from capture import parse_stream
    # 'ended' / 'sending' are NOT the END token: no truncation
    lines = ["boot ok", "frequency_hz,real,imag", "1000,3,4",
             "calibration ended", "2000,6,8", "sending done", "3000,9,12", "END", "4000,1,1"]
    rows = parse_stream(lines)
    assert rows == [(1000, 3.0, 4.0), (2000, 6.0, 8.0), (3000, 9.0, 12.0)]  # stops at END only


def test_model_single_dirty_sample_clear_error(tmp_path):
    # 2 controls, 1 yeast -> LOO would crash; must raise a clear error instead
    for i in (1, 2):
        write(tmp_path, f"control_na_0{i}.csv", "frequency_hz,real,imag\n1000,3,4\n2000,6,8\n1500,4,5\n")
    write(tmp_path, "yeast_med_01.csv", "frequency_hz,real,imag\n1000,9,4\n2000,2,8\n1500,7,5\n")
    ft = eis.feature_table(eis.ingest_folder(tmp_path))
    with pytest.raises(ValueError, match="2 samples per class"):
        eis.clean_vs_dirty(ft)


def test_report_builds(tmp_path):
    synth.write_dataset(tmp_path, repeats=2)
    m = eis.ingest_folder(tmp_path)
    out = eis.build_report(m, tmp_path / "out")
    html = out.read_text()
    assert out.exists() and "EIS prototype" in html and "data:image/png" in html
