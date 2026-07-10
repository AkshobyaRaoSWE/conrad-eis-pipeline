#include "ad5933.h"
#include <Wire.h>

// ---- low-level I2C ----------------------------------------------------------

bool AD5933::writeReg(uint8_t reg, uint8_t val) {
    Wire.beginTransmission(AD5933_ADDR);
    Wire.write(reg);
    Wire.write(val);
    return Wire.endTransmission() == 0;
}

bool AD5933::readReg(uint8_t reg, uint8_t &val) {
    // set address pointer, then read one byte
    Wire.beginTransmission(AD5933_ADDR);
    Wire.write(AD5933_PTR_CMD);
    Wire.write(reg);
    if (Wire.endTransmission() != 0) return false;
    if (Wire.requestFrom((int)AD5933_ADDR, 1) != 1) return false;
    val = Wire.read();
    return true;
}

bool AD5933::write24(uint8_t reg, uint32_t code) {
    return writeReg(reg,     (code >> 16) & 0xFF) &&
           writeReg(reg + 1, (code >> 8)  & 0xFF) &&
           writeReg(reg + 2,  code        & 0xFF);
}

bool AD5933::write16(uint8_t reg, uint16_t val) {
    return writeReg(reg,     (val >> 8) & 0xFF) &&
           writeReg(reg + 1,  val       & 0xFF);
}

bool AD5933::read16(uint8_t reg, int16_t &val) {
    uint8_t hi, lo;
    if (!readReg(reg, hi) || !readReg(reg + 1, lo)) return false;
    val = (int16_t)(((uint16_t)hi << 8) | lo);   // registers are two's-complement
    return true;
}

bool AD5933::issueCommand(uint8_t cmd) {
    // keep range/gain bits (low nibble of _ctrlHigh), replace command nibble
    _ctrlHigh = (cmd & 0xF0) | (_ctrlHigh & 0x0F);
    return writeReg(AD5933_REG_CONTROL_HB, _ctrlHigh);
}

bool AD5933::waitStatus(uint8_t mask, uint32_t timeout_ms) {
    uint32_t t0 = millis();
    uint8_t s = 0;
    while (millis() - t0 < timeout_ms) {
        if (readReg(AD5933_REG_STATUS, s) && (s & mask)) return true;
        delay(1);
    }
    return false;
}

// ---- public API -------------------------------------------------------------

bool AD5933::begin() {
    Wire.beginTransmission(AD5933_ADDR);
    if (Wire.endTransmission() != 0) return false;   // no ACK -> not present
    return reset();
}

bool AD5933::reset() {
    // internal clock + reset bit
    return writeReg(AD5933_REG_CONTROL_LB, AD5933_CTRL_RESET);
}

bool AD5933::configureSweep(double startHz, double stepHz, uint16_t nPoints,
                            uint16_t settling, uint8_t range, uint8_t gain) {
    if (nPoints < 1)   nPoints = 1;
    if (nPoints > 511) nPoints = 511;               // 9-bit increment count
    if (settling > 511) settling = 511;             // 9-bit count; keep out of the D10-D9 multiplier field
    _startHz = startHz;
    _stepHz  = stepHz;
    _nPoints = nPoints;
    _idx     = 0;
    _ctrlHigh = AD5933_CMD_NOP | (range & 0x06) | (gain & 0x01);

    bool ok = true;
    ok &= writeReg(AD5933_REG_CONTROL_LB, 0x00);    // internal clock, clear reset
    ok &= writeReg(AD5933_REG_CONTROL_HB, _ctrlHigh);
    ok &= write24(AD5933_REG_START_FREQ, ad5933_freq_code(_startHz, _mclk));
    ok &= write24(AD5933_REG_FREQ_INC,   ad5933_freq_code(_stepHz,  _mclk));
    ok &= write16(AD5933_REG_NUM_INCR,   (uint16_t)(_nPoints - 1)); // increments = points-1
    ok &= write16(AD5933_REG_SETTLING,   settling);
    return ok;
}

bool AD5933::startSweep() {
    _idx = 0;
    if (!issueCommand(AD5933_CMD_STANDBY)) return false;
    // Pulse reset (control-LB D4): clears the state machine and status register so a
    // repeat sweep can't read the previous run's stale DATA_VALID / SWEEP_COMPLETE.
    // Frequency/settling registers are preserved. Then release reset (internal clock).
    if (!writeReg(AD5933_REG_CONTROL_LB, AD5933_CTRL_RESET)) return false;
    if (!writeReg(AD5933_REG_CONTROL_LB, 0x00))             return false;
    if (!issueCommand(AD5933_CMD_INIT_START)) return false; // settle at start freq
    delay(2);
    return issueCommand(AD5933_CMD_START_SWEEP);
}

bool AD5933::nextPoint(SweepPoint &out) {
    if (!waitStatus(AD5933_STATUS_DATA_VALID)) return false;  // DFT ready
    int16_t re, im;
    if (!read16(AD5933_REG_REAL, re) || !read16(AD5933_REG_IMAG, im)) return false;
    out.real = re;
    out.imag = im;
    out.frequency_hz = _startHz + (double)_idx * _stepHz;
    _idx++;
    if (!sweepComplete()) issueCommand(AD5933_CMD_INCREMENT); // advance to next freq
    return true;
}

bool AD5933::sweepComplete() {
    uint8_t s = 0;
    return readReg(AD5933_REG_STATUS, s) && (s & AD5933_STATUS_SWEEP_DONE);
}

bool AD5933::readTemperature(double &celsius) {
    if (!issueCommand(AD5933_CMD_MEAS_TEMP)) return false;
    if (!waitStatus(AD5933_STATUS_TEMP_VALID)) return false;
    int16_t raw;
    if (!read16(AD5933_REG_TEMP, raw)) return false;
    // 14-bit two's-complement, 1/32 deg C per LSB (datasheet p.12)
    if (raw & 0x2000) celsius = (raw - 16384) / 32.0;
    else              celsius = raw / 32.0;
    return true;
}
