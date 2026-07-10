// AD5933 numeric core -- pure C, NO Arduino/hardware includes.
//
// Isolated here so the datasheet math (frequency codes, calibration, impedance)
// can be unit-tested on a host with g++ (see ../test/test_math.cpp) and stays
// identical to what runs on the ESP32. The Python pipeline derives impedance the
// same way (impedance_ohm = 1 / (gain_factor * magnitude)); these must agree.
#ifndef AD5933_MATH_H
#define AD5933_MATH_H

#include <stdint.h>
#include <math.h>

// Internal oscillator. The DDS core is clocked at MCLK/4 (datasheet p.11).
// If an external clock is wired to MCLK, pass its frequency instead.
#define AD5933_INTERNAL_CLK_HZ 16776000.0
#define AD5933_POW_2_27        134217728.0   // 2^27, the DDS accumulator scale

// 24-bit frequency code programmed into the start-frequency / increment registers.
// code = (f / (MCLK/4)) * 2^27, rounded, clamped to 24 bits (datasheet eq. p.24).
static inline uint32_t ad5933_freq_code(double freq_hz, double mclk_hz) {
    double code = (freq_hz / (mclk_hz / 4.0)) * AD5933_POW_2_27 + 0.5;
    if (code < 0.0) code = 0.0;
    if (code > 16777215.0) code = 16777215.0;   // 0xFFFFFF, 24-bit max
    return (uint32_t)code;
}

// DFT magnitude from the signed real/imaginary registers.
static inline double ad5933_magnitude(int16_t real, int16_t imag) {
    return sqrt((double)real * (double)real + (double)imag * (double)imag);
}

// Gain factor from a calibration sweep on a known resistor:
// GF = 1 / (magnitude * R_cal)  (datasheet "Gain Factor Setup", p.15).
static inline double ad5933_gain_factor(double magnitude, double r_cal_ohms) {
    return 1.0 / (magnitude * r_cal_ohms);
}

// Unknown impedance from magnitude and a known gain factor.
static inline double ad5933_impedance(double magnitude, double gain_factor) {
    return 1.0 / (gain_factor * magnitude);
}

// Phase in degrees (raw, includes the system phase; subtract the calibration
// phase for true sample phase). Matches numpy.degrees(arctan2(imag, real)).
static inline double ad5933_phase_deg(int16_t real, int16_t imag) {
    return atan2((double)imag, (double)real) * 180.0 / M_PI;
}

#endif // AD5933_MATH_H
