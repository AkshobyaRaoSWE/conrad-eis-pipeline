# EIS water-fingerprint pipeline

Software & data lane for the Conrad water-safety prototype. Turns AD5933 impedance
sweeps into a labeled master table, figures, a noise/repeatability report, and an
optional clean-vs-dirty check. Built to run **before** the hardware is assembled
(against synthetic sweeps) and unchanged **after** (point it at real CSVs).

## Setup

    pip install -r requirements.txt

## The one contract that matters

Firmware writes **one CSV per sweep** into `data/raw/`. Format and naming are in
[`SWEEP_FORMAT.md`](SWEEP_FORMAT.md) — that's the agreement with Ian's firmware.
Minimum columns: `frequency_hz,real,imag`. Everything else is derived or optional.

## Commands

    python cli.py synth          # generate synthetic sweeps in data/raw (no hardware)
    python cli.py ingest         # data/raw/*.csv -> data/out/master.csv + features.csv
    python cli.py plot <id>      # single-sweep sanity plot (is the curve smooth, not noise?)
    python cli.py overlay        # overlay all sweeps + feature scatter (do samples separate?)
    python cli.py noise          # repeatability / noise floor (is the rig trustworthy?)
    python cli.py model          # optional clean-vs-dirty leave-one-out check
    python cli.py demo           # all of the above, end to end

Add `--gain-factor <float>` to convert magnitude to ohms (see calibration in the format doc).

## When real data arrives

1. Ian's firmware saves sweeps into `data/raw/` following the naming convention.
2. `python cli.py ingest` — new files auto-join the table, labeled from name/header/manifest.
3. `overlay` / `noise` / `model` — same commands, real numbers.

Nothing about the workflow changes between synthetic and real data; that's the point.
Delete `data/raw/*` (synthetic) once real sweeps exist.

## Layout

    eis/
      io.py        raw CSV -> master table (parsing, labeling, derived columns)
      synth.py     physics-plausible fake sweeps for testing (Randles cell model)
      features.py  sweep -> small fixed feature vector
      plots.py     single sweep, overlays, feature scatter (dark, video-ready)
      noise.py     repeatability, noise floor, class separation
      model.py     optional tiny logistic-regression classifier
    cli.py         command-line front end
    data/raw/      per-sweep CSVs land here   (+ optional manifest.csv)
    data/out/      generated tables and figures

## Notes for fall

- `features.py:KEY_FREQS` and `sweep_features` are where the feature set grows for the real model.
- `model.py` is a placeholder sanity check (leave-one-out on a tiny set), not the fall model.
- `synth.py` is scaffolding only — it makes no claim about real water and gets deleted once
  real data exists.
