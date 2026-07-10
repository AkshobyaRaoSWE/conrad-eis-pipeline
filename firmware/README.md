# Firmware — ESP32 + AD5933 (Ian's lane)

Runs an electrochemical impedance sweep and prints one sweep in the exact CSV
format the pipeline ingests ([`../SWEEP_FORMAT.md`](../SWEEP_FORMAT.md)):

    # label: yeast
    # points: 100
    frequency_hz,real,imag
    1000,15234,-4021
    ...
    100000,8801,-1120
    END

The chip emits raw signed `real`/`imag` DFT registers; the pipeline derives
magnitude, phase, and (after calibration) impedance in ohms. Nothing is computed
twice on two sides.

## Wiring (ESP32 dev board ↔ AD5933 breakout)

| AD5933 | ESP32   | note |
|--------|---------|------|
| VDD    | 3V3     | 3.3 V only |
| GND    | GND     | common ground |
| SDA    | GPIO 21 | I2C data (override with `-D I2C_SDA=`) |
| SCL    | GPIO 22 | I2C clock (override with `-D I2C_SCL=`) |
| VOUT   | cell +  | excitation into the sample cell |
| VIN    | cell −  | response back through the feedback resistor (RFB) |

The AD5933 I2C address is fixed at `0x0D`. Use 3.3 V logic (the ESP32 is not 5 V tolerant).

## Build & flash

**PlatformIO** (recommended):

    cd firmware
    pio run                 # compile
    pio run -t upload       # flash
    pio device monitor -b 115200

**Arduino IDE:** open `src/main.cpp` (add `ad5933.cpp/.h`, `ad5933_math.h`),
board = "ESP32 Dev Module", 115200 baud.

## Use

Over serial @ 115200, send one letter:

- `r` — run a sweep and print pipeline-ready CSV
- `c` — calibration sweep on the `R_CAL_OHMS` reference resistor; prints a
  `# gain_factor: …` line to feed `cli.py --gain-factor` (or a file header)
- `t` — chip temperature
- `h` — help

`../capture.py` drives `r` automatically and writes a labeled file into `../data/raw/`:

    cd .. && python capture.py --port /dev/tty.usbserial-XXXX --label yeast --conc med --rep 2
    python cli.py ingest

## Calibration flow

1. Wire a known resistor (`R_CAL_OHMS`, default 10 kΩ) across the cell terminals.
2. Send `c`. Read the printed `# gain_factor:`.
3. Measure real samples with `r` / `capture.py`.
4. Ingest with that factor: `python cli.py --gain-factor <value> ingest` → `impedance_ohm` column in ohms.

Gain factor is taken as the sweep-mean here; per-frequency calibration is a fall refinement.

## Sweep configuration

Edit the defines at the top of `src/main.cpp`: `SWEEP_START_HZ`, `SWEEP_STEP_HZ`,
`SWEEP_POINTS` (≤ 511), `SWEEP_SETTLING`, `R_CAL_OHMS`. Default is a linear
1 kHz → 100 kHz sweep in 1 kHz steps (hits every feature frequency the pipeline uses).
The AD5933 does linear sweeps natively; log spacing (better at low frequency) is a
fall upgrade via stacked sub-sweeps.

## Host test (no hardware)

The datasheet math (frequency codes, calibration, impedance) is isolated in
`src/ad5933_math.h` and unit-tested with plain g++ — same formulas the Python
pipeline uses, so the two lanes can't drift:

    cd firmware/test && make

## Files

    src/ad5933_math.h   pure numeric core (host-testable, shared with the pipeline's math)
    src/ad5933.h/.cpp   I2C driver (register map per AD5933 datasheet Rev. E)
    src/main.cpp        serial command loop + CSV output
    test/test_math.cpp  host unit test (g++)
    platformio.ini      ESP32 build
