#!/usr/bin/env python3
"""Command-line front end for the EIS pipeline.

    python cli.py synth                 # make synthetic test data in data/raw
    python cli.py ingest                # raw CSVs -> data/out/master.csv + features.csv
    python cli.py plot <sample_id>      # single-sweep sanity plot
    python cli.py overlay               # overlay all sweeps (magnitude + phase)
    python cli.py noise                 # repeatability / noise floor
    python cli.py model                 # optional clean-vs-dirty check
    python cli.py demo                  # run the whole thing end to end

Global option: --gain-factor <float> to convert magnitude to ohms.
Run with no hardware today; point at data/raw once real CSVs land -- same commands.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eis  # noqa: E402

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "out"


def _master(gain):
    return eis.ingest_folder(RAW, gain_factor=gain)


def cmd_synth(args):
    from eis import synth
    files = synth.write_dataset(RAW, repeats=args.repeats)
    print(f"wrote {len(files)} synthetic sweeps to {RAW}")


def cmd_ingest(args):
    OUT.mkdir(parents=True, exist_ok=True)
    master = _master(args.gain_factor)
    feats = eis.feature_table(master)
    master.to_csv(OUT / "master.csv", index=False)
    feats.to_csv(OUT / "features.csv", index=False)
    n_sweeps = master["sample_id"].nunique()
    print(f"ingested {n_sweeps} sweeps, {len(master)} rows")
    print(f"  {OUT/'master.csv'}")
    print(f"  {OUT/'features.csv'}")
    print("labels:", ", ".join(f"{k}×{v}" for k, v in
          feats["label"].value_counts().items()))


def cmd_plot(args):
    master = _master(args.gain_factor)
    sub = master[master["sample_id"] == args.sample_id]
    if sub.empty:
        sys.exit(f"no sweep with sample_id={args.sample_id!r}")
    p = eis.plot_sweep(sub, OUT / f"sweep_{args.sample_id}.png")
    print("wrote", p)


def cmd_overlay(args):
    master = _master(args.gain_factor)
    p1 = eis.overlay(master, OUT / "overlay_magnitude.png", value="magnitude")
    p2 = eis.overlay(master, OUT / "overlay_phase.png", value="phase_deg")
    feats = eis.feature_table(master)
    p3 = eis.feature_scatter(feats, OUT / "scatter_features.png",
                             x="mag_20000", y="phase_peak")
    for p in (p1, p2, p3):
        print("wrote", p)


def cmd_noise(args):
    master = _master(args.gain_factor)
    rep = eis.repeatability(master)
    summ = eis.noise_summary(rep)
    OUT.mkdir(parents=True, exist_ok=True)
    rep.to_csv(OUT / "repeatability.csv", index=False)
    print("noise floor (median CV% per feature, best first):")
    with pd.option_context("display.max_rows", None):
        print(summ.to_string(index=False))
    # headline separation: clean control vs yeast on a strong feature
    labels = set(master["label"])
    if {"control", "yeast"} <= labels:
        sep = eis.separation(master, "phase_peak", "control", "yeast")
        print(f"\ncontrol vs yeast on phase_peak: "
              f"{sep['separation']:.1f} noise-widths apart")


def cmd_model(args):
    master = _master(args.gain_factor)
    feats = eis.feature_table(master)
    acc, conf, detail = eis.clean_vs_dirty(feats)
    print(f"clean-vs-dirty leave-one-out accuracy: {acc*100:.0f}%")
    print(f"  tp={conf['tp']} fn={conf['fn']} fp={conf['fp']} tn={conf['tn']}"
          f"   (fn = missed contamination -- keep this at 0)")
    OUT.mkdir(parents=True, exist_ok=True)
    detail.to_csv(OUT / "model_predictions.csv", index=False)


def cmd_demo(args):
    print("== synth =="); cmd_synth(args)
    print("\n== ingest =="); cmd_ingest(args)
    print("\n== overlay =="); cmd_overlay(args)
    print("\n== noise =="); cmd_noise(args)
    print("\n== model =="); cmd_model(args)
    print(f"\ndone. figures + tables in {OUT}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gain-factor", type=float, default=None,
                    help="AD5933 gain factor to convert magnitude to ohms")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("synth", help="write synthetic test sweeps")
    s.add_argument("--repeats", type=int, default=3)
    s.set_defaults(func=cmd_synth)

    sub.add_parser("ingest", help="raw -> master + features").set_defaults(func=cmd_ingest)

    s = sub.add_parser("plot", help="single sweep plot")
    s.add_argument("sample_id")
    s.set_defaults(func=cmd_plot)

    sub.add_parser("overlay", help="overlay all sweeps").set_defaults(func=cmd_overlay)
    sub.add_parser("noise", help="repeatability / noise floor").set_defaults(func=cmd_noise)
    sub.add_parser("model", help="optional clean-vs-dirty model").set_defaults(func=cmd_model)

    s = sub.add_parser("demo", help="run everything end to end")
    s.add_argument("--repeats", type=int, default=3)
    s.set_defaults(func=cmd_demo)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
