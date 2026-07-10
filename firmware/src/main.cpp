// Conrad EIS prototype -- ESP32 + AD5933 firmware (Ian's lane).
//
// Runs an impedance sweep and prints one sweep in the exact CSV format the
// pipeline ingests (see ../../SWEEP_FORMAT.md): optional `# key: value` header,
// then `frequency_hz,real,imag`, then rows, then a lone `END`.
//
// Serial @ 115200. Commands (one letter + Enter):
//   r  run a sweep and print it (raw real/imag; pipeline derives the rest)
//   c  calibration sweep on a known resistor -> prints per-point + a gain_factor
//   t  read chip temperature
//   h  help
//
// capture.py drives 'r' automatically; or use the Arduino Serial Monitor by hand.

#include <Arduino.h>
#include <Wire.h>
#include "ad5933.h"

// ---- wiring / sweep configuration ------------------------------------------
#ifndef I2C_SDA
#define I2C_SDA 21          // ESP32 default SDA
#endif
#ifndef I2C_SCL
#define I2C_SCL 22          // ESP32 default SCL
#endif

#define SWEEP_START_HZ 1000.0
#define SWEEP_STEP_HZ  1000.0     // linear: 1 kHz .. 100 kHz in 1 kHz steps
#define SWEEP_POINTS   100
#define SWEEP_SETTLING 15         // excitation cycles to settle per point
#define R_CAL_OHMS     10000.0    // reference resistor used for `c` calibration

AD5933 sensor;

static void printHelp() {
    Serial.println(F("# commands: r=run sweep  c=calibrate  t=temp  h=help"));
}

// Print one sweep as pipeline-ready CSV. `label` optional (empty -> none).
static void runSweep(const char *label, bool calibrate) {
    if (!sensor.configureSweep(SWEEP_START_HZ, SWEEP_STEP_HZ, SWEEP_POINTS, SWEEP_SETTLING)) {
        Serial.println(F("# ERROR: configureSweep failed"));
        return;
    }
    if (!sensor.startSweep()) {
        Serial.println(F("# ERROR: startSweep failed"));
        return;
    }

    // header
    if (label && label[0]) Serial.printf("# label: %s\n", label);
    Serial.printf("# points: %u\n# start_hz: %.0f\n# step_hz: %.0f\n",
                  sensor.points(), sensor.startHz(), sensor.stepHz());

    // For calibration we accumulate a gain factor from the magnitude at each point.
    double gfSum = 0.0;
    uint16_t gfN = 0;

    Serial.println(F("frequency_hz,real,imag"));
    SweepPoint p;
    uint16_t guard = 0;
    while (guard++ < 2000) {
        if (!sensor.nextPoint(p)) {
            Serial.println(F("# ERROR: point read timed out"));
            break;
        }
        Serial.printf("%.0f,%d,%d\n", p.frequency_hz, p.real, p.imag);
        if (calibrate) {
            double mag = ad5933_magnitude(p.real, p.imag);
            if (mag > 0) { gfSum += ad5933_gain_factor(mag, R_CAL_OHMS); gfN++; }
        }
        if (sensor.sweepComplete()) break;
    }
    Serial.println(F("END"));

    if (calibrate && gfN) {
        // mean gain factor across the sweep; single-value calibration for the pipeline
        Serial.printf("# gain_factor: %.6e  (R_cal=%.0f ohm, n=%u)\n",
                      gfSum / gfN, R_CAL_OHMS, gfN);
    }
}

void setup() {
    Serial.begin(115200);
    delay(200);
    Wire.begin(I2C_SDA, I2C_SCL);
    Wire.setClock(100000);

    Serial.println(F("# Conrad EIS -- ESP32 + AD5933"));
    if (!sensor.begin()) {
        Serial.println(F("# ERROR: AD5933 not found on I2C (0x0D). Check wiring/power."));
    } else {
        Serial.println(F("# AD5933 detected."));
    }
    printHelp();
}

void loop() {
    if (!Serial.available()) return;
    int c = Serial.read();
    switch (c) {
        case 'r': runSweep("", false); break;
        case 'c':
            Serial.printf("# CALIBRATION on %.0f ohm reference\n", R_CAL_OHMS);
            runSweep("calibration", true);
            break;
        case 't': {
            double tc;
            if (sensor.readTemperature(tc)) Serial.printf("# temperature_c: %.2f\n", tc);
            else                            Serial.println(F("# ERROR: temp read failed"));
            break;
        }
        case 'h': printHelp(); break;
        case '\n': case '\r': break;      // ignore line endings
        default: break;
    }
}
