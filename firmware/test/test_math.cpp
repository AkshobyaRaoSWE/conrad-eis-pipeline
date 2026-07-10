// Host unit test for the AD5933 numeric core. Builds with plain g++ (no hardware):
//     c++ -std=c++11 -I../src test_math.cpp -o test_math && ./test_math
// Cross-checks the same formulas the Python pipeline uses.
#include "../src/ad5933_math.h"
#include <cstdio>
#include <cmath>

static int failures = 0;
static void check(const char *name, double got, double want, double tol) {
    bool ok = std::fabs(got - want) <= tol;
    if (!ok) failures++;
    printf("[%s] %s  got=%.6f want=%.6f tol=%.6g\n",
           ok ? "PASS" : "FAIL", name, got, want, tol);
}

int main() {
    const double MCLK = AD5933_INTERNAL_CLK_HZ;

    // Frequency code: f / (MCLK/4) * 2^27. Hand value for 1 kHz.
    double want1k = (1000.0 / (MCLK / 4.0)) * 134217728.0;
    check("freq_code(1kHz)", (double)ad5933_freq_code(1000.0, MCLK), std::floor(want1k + 0.5), 0.0);
    // 30 kHz sanity + monotonic + 24-bit clamp at the top.
    check("freq_code(30kHz)", (double)ad5933_freq_code(30000.0, MCLK),
          std::floor((30000.0 / (MCLK / 4.0)) * 134217728.0 + 0.5), 0.0);
    check("freq_code clamps to 24-bit", (double)ad5933_freq_code(1e9, MCLK), 16777215.0, 0.0);

    // Magnitude / phase against the pipeline's numpy convention.
    check("magnitude(3,-4)", ad5933_magnitude(3, -4), 5.0, 1e-12);
    check("phase_deg(3,-4)", ad5933_phase_deg(3, -4), -53.13010235, 1e-6);

    // Calibration round-trip: a known resistor calibrates GF, then the SAME reading
    // must read back as that resistor's impedance. This is the pipeline's
    // impedance_ohm = 1/(GF*magnitude) identity.
    int16_t re = 12000, im = -9000;                 // arbitrary cal reading
    double mag = ad5933_magnitude(re, im);          // 15000
    double gf  = ad5933_gain_factor(mag, 10000.0);  // calibrate on 10k
    check("cal round-trip -> 10k", ad5933_impedance(mag, gf), 10000.0, 1e-6);
    // A reading with half the magnitude reads as double the impedance.
    check("half magnitude -> 2x ohms", ad5933_impedance(mag / 2.0, gf), 20000.0, 1e-6);

    printf("\n%s (%d failure%s)\n", failures ? "FAILED" : "ALL PASS",
           failures, failures == 1 ? "" : "s");
    return failures ? 1 : 0;
}
