"""Cross-lane test: firmware serial output must flow through capture -> pipeline.

Simulates exactly what main.cpp prints over serial (header comments, the
`frequency_hz,real,imag` block, boot/log chatter, and a trailing END), runs it
through capture.parse_stream, writes the file capture would write, and confirms
the pipeline ingests it and resolves every KEY_FREQ on the AD5933's linear grid.
"""

import math

import numpy as np
import pandas as pd

import eis
from capture import parse_stream
from eis.features import KEY_FREQS


def _firmware_lines():
    """Byte-for-byte what the ESP32 prints for one `r` sweep: 1 kHz..100 kHz, 1 kHz steps."""
    lines = [
        "# Conrad EIS -- ESP32 + AD5933",   # boot banner (chatter before header)
        "# AD5933 detected.",
        "# label: yeast",
        "# points: 100",
        "# start_hz: 1000",
        "# step_hz: 1000",
        "frequency_hz,real,imag",
    ]
    for i in range(100):
        f = 1000 + i * 1000
        # a smooth, monotone-ish admittance-like reading so QC stays clean
        w = 2 * math.pi * f
        y = 1e4 / (1 + (5e3 / (1 + 1j * w * 3500 * 4.5e-8)))
        lines.append(f"{f},{int(y.real)},{int(y.imag)}")
    lines.append("sweep ended")   # <- contains 'end' substring; must NOT truncate
    lines.append("END")           # <- the real terminator
    lines.append("100000,999,999")  # stray line after END: must be ignored
    return lines


def test_firmware_output_flows_into_pipeline(tmp_path):
    rows = parse_stream(_firmware_lines())
    assert len(rows) == 100                         # 'sweep ended' did not truncate
    assert rows[0][0] == 1000 and rows[-1][0] == 100000

    # write the file capture.py would write, then ingest it
    raw = tmp_path
    with (raw / "yeast_med_01.csv").open("w") as fh:
        fh.write("# sample_id: yeast_med_01\n# label: yeast\nfrequency_hz,real,imag\n")
        for f, re_, im_ in rows:
            fh.write(f"{f},{re_},{im_}\n")

    master = eis.ingest_folder(raw)
    assert master["file"].nunique() == 1
    assert master["label"].iloc[0] == "yeast"

    # every KEY_FREQ lands exactly on the 1 kHz linear grid -> no NaN features
    feats = eis.feature_table(master)
    for kf in KEY_FREQS:
        assert np.isfinite(feats[f"mag_{kf}"].iloc[0]), f"mag_{kf} missing on linear grid"

    # a clean smooth sweep passes QC (no spike/flat false positives)
    from eis.qc import validate_sweep
    assert not any(i.severity == "error" for i in validate_sweep(master))


def test_firmware_grid_hits_all_key_freqs():
    # the configured sweep (start 1000, step 1000, 100 pts) must reach exactly 100 kHz
    freqs = [1000 + i * 1000 for i in range(100)]
    assert freqs[-1] == 100000
    for kf in KEY_FREQS:
        assert kf in freqs
