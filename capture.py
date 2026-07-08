#!/usr/bin/env python3
"""Capture one sweep from the ESP32 over serial into a format-correct CSV.

Bridges Ian's firmware to the pipeline: the ESP32 prints `frequency_hz,real,imag`
lines over USB serial; this reads them and writes a labeled file into data/raw/ that
`cli.py ingest` picks up. Needs pyserial (`pip install pyserial`) and real hardware.

    python capture.py --port /dev/tty.usbserial-XXXX --label yeast --conc med --rep 2
    python capture.py --list                     # list available serial ports

The firmware should print a header line `frequency_hz,real,imag`, then one CSV row
per frequency, then a line containing `END` (or just stop) to mark the sweep done.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAW = Path(__file__).resolve().parent / "data" / "raw"


def _require_serial():
    try:
        import serial  # noqa
        from serial.tools import list_ports  # noqa
        return serial, list_ports
    except ImportError:
        sys.exit("pyserial not installed. Run: pip install pyserial")


def list_ports_cmd():
    _, list_ports = _require_serial()
    ports = list(list_ports.comports())
    if not ports:
        print("no serial ports found")
        return
    for p in ports:
        print(f"{p.device}\t{p.description}")


def capture(port, baud, label, conc, rep, additives, out_dir=RAW, timeout=30):
    """Read one sweep from `port` and write data/raw/<label>_<conc>_<rep>.csv."""
    serial, _ = _require_serial()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{label}_{conc}_{int(rep):02d}.csv"
    path = out_dir / fname

    rows, started = [], False
    with serial.Serial(port, baud, timeout=timeout) as ser:
        print(f"listening on {port} @ {baud} ... (waiting for sweep)")
        while True:
            raw = ser.readline()
            if not raw:  # timeout
                break
            line = raw.decode(errors="replace").strip()
            if not line:
                continue
            low = line.lower()
            if "end" in low and started:
                break
            if low.startswith("frequency"):  # firmware header line
                started = True
                continue
            parts = line.split(",")
            if len(parts) >= 3:
                try:
                    f, re_, im_ = float(parts[0]), float(parts[1]), float(parts[2])
                    rows.append((int(f), re_, im_))
                    started = True
                except ValueError:
                    continue  # noise / boot log line, skip

    if not rows:
        sys.exit("no sweep data received (check firmware is running and printing CSV)")

    with path.open("w") as fh:
        fh.write(f"# sample_id: {label}_{conc}_{int(rep):02d}\n")
        fh.write(f"# label: {label}\n# concentration: {conc}\n# repeat: {int(rep)}\n")
        fh.write(f"# additives: {additives}\n")
        fh.write("frequency_hz,real,imag\n")
        for f, re_, im_ in rows:
            fh.write(f"{f},{re_},{im_}\n")
    print(f"wrote {len(rows)} points -> {path}")
    print("next: python cli.py ingest")
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="list serial ports and exit")
    ap.add_argument("--port")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--label", default="sample")
    ap.add_argument("--conc", default="na")
    ap.add_argument("--rep", default=1)
    ap.add_argument("--additives", default="none")
    ap.add_argument("--timeout", type=int, default=30)
    args = ap.parse_args()

    if args.list:
        list_ports_cmd()
        return
    if not args.port:
        ap.error("--port is required (use --list to find it)")
    capture(args.port, args.baud, args.label, args.conc, args.rep,
            args.additives, timeout=args.timeout)


if __name__ == "__main__":
    main()
