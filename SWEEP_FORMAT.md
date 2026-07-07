# Sweep CSV format (firmware ↔ pipeline contract)

This is the agreement between Ian's firmware and Akshobya's pipeline. One sweep = one file.
Keep it stable; if it changes, both sides update together.

## One file per measurement

The ESP32 + AD5933 writes **one CSV per sweep** into `data/raw/`.

### Columns (required)

    frequency_hz,real,imag

- `frequency_hz` — sweep frequency in Hz (integer or float).
- `real`, `imag` — the AD5933 real and imaginary registers for that frequency
  (raw signed integers straight off the chip are fine).

The pipeline derives everything else:

- `magnitude = hypot(real, imag)`
- `phase_deg = degrees(atan2(imag, real))`
- `impedance_ohm = 1 / (gain_factor * magnitude)`  ← only if a gain factor is known (see calibration)

If the firmware already computes `magnitude`, `phase_deg`, or `impedance_ohm`, it may add those
columns and the pipeline will use them instead of recomputing. Extra columns are ignored, not an error.

### Optional header lines

Any leading lines starting with `#` are metadata, `# key: value`:

    # sample_id: yeast_med_02
    # label: yeast
    # concentration: med
    # repeat: 2
    # additives: none
    # gain_factor: 3.145e-9
    # temperature_c: 22.4
    # timestamp: 2026-07-09T14:03:11
    frequency_hz,real,imag
    1000,15234,-4021
    ...

Header values override anything parsed from the filename.

## Filename convention (auto-labeling)

When there is no header, the pipeline labels the sweep from the filename. Convention:

    <label>_<concentration>_<repeat>[_<anything>].csv

Examples:

    control_na_01.csv          -> label=control, concentration=na,  repeat=1
    tap_na_03.csv              -> label=tap,     concentration=na,  repeat=3
    yeast_med_02.csv           -> label=yeast,   concentration=med, repeat=2
    yeast_high_01_run2.csv     -> label=yeast,   concentration=high, repeat=1  (trailing part ignored)

Anything the convention can't parse still ingests; unknown fields become empty and the file
name becomes the sample_id. Nothing is ever dropped silently.

## manifest.csv (optional, authoritative)

Ariston's log can drop a `data/raw/manifest.csv` to override/augment labels without renaming files:

    filename,label,concentration,repeat,additives,notes
    scan_0007.csv,yeast,med,2,salt,"cloudy sample"

Manifest values win over filename parsing but lose to in-file `#` headers
(header is closest to the measurement, so it's most trusted).

## Calibration (gain factor)

AD5933 magnitude is in arbitrary units until calibrated. Measure a known resistor `R_cal`,
read its `magnitude_cal`, then `gain_factor = 1 / (magnitude_cal * R_cal)`. Put it in the header
(`# gain_factor:`) or pass `--gain-factor` to the CLI. Without it the pipeline works in **raw
magnitude units** — still fine for telling samples apart, which is the summer goal.
