// AD5933 impedance-converter driver for ESP32 (Arduino / Wire I2C).
// Register map and command set per Analog Devices AD5933 datasheet (Rev. E).
#ifndef AD5933_H
#define AD5933_H

#include <Arduino.h>
#include "ad5933_math.h"

// I2C
#define AD5933_ADDR            0x0D   // fixed 7-bit device address

// Register map
#define AD5933_REG_CONTROL_HB  0x80   // control high byte (command + range + gain)
#define AD5933_REG_CONTROL_LB  0x81   // control low byte  (reset + clock select)
#define AD5933_REG_START_FREQ  0x82   // 0x82..0x84, 24-bit
#define AD5933_REG_FREQ_INC    0x85   // 0x85..0x87, 24-bit
#define AD5933_REG_NUM_INCR    0x88   // 0x88..0x89, 9-bit (max 511)
#define AD5933_REG_SETTLING    0x8A   // 0x8A..0x8B, settling-time cycles
#define AD5933_REG_STATUS      0x8F
#define AD5933_REG_TEMP        0x92   // 0x92..0x93, signed
#define AD5933_REG_REAL        0x94   // 0x94..0x95, signed
#define AD5933_REG_IMAG        0x96   // 0x96..0x97, signed

// Address-pointer I2C command (used by single-byte reads). Note: the byte value
// 0xB0 equals the standby command value by datasheet design, but they live in
// different contexts (I2C command byte vs control-register value) and never mix.
// Block read/write opcodes (0xA1/0xA0) are unused here -- we read one byte at a time.
#define AD5933_PTR_CMD         0xB0   // set address pointer

// Control high-byte command nibble (D15..D12)
#define AD5933_CMD_NOP         0x00
#define AD5933_CMD_INIT_START  0x10   // initialize with start frequency
#define AD5933_CMD_START_SWEEP 0x20
#define AD5933_CMD_INCREMENT   0x30
#define AD5933_CMD_REPEAT      0x40
#define AD5933_CMD_MEAS_TEMP   0x90
#define AD5933_CMD_POWER_DOWN  0xA0
#define AD5933_CMD_STANDBY     0xB0

// Output excitation voltage range (D10..D9)
#define AD5933_RANGE_2VPP      0x00
#define AD5933_RANGE_200MVPP   0x02
#define AD5933_RANGE_400MVPP   0x04
#define AD5933_RANGE_1VPP      0x06
// PGA gain (D8): 1 => x1, 0 => x5
#define AD5933_GAIN_X1         0x01
#define AD5933_GAIN_X5         0x00

// Control low-byte bits
#define AD5933_CTRL_RESET      0x10   // D4
#define AD5933_CTRL_EXT_CLOCK  0x08   // D3 (0 = internal oscillator)

// Status register bits (0x8F)
#define AD5933_STATUS_TEMP_VALID  0x01
#define AD5933_STATUS_DATA_VALID  0x02   // real/imag ready (DFT done)
#define AD5933_STATUS_SWEEP_DONE  0x04

struct SweepPoint {
    double  frequency_hz;
    int16_t real;
    int16_t imag;
};

class AD5933 {
public:
    bool begin();                              // probe device on I2C
    bool reset();

    // Configure a linear sweep: nPoints from startHz in stepHz increments.
    // settling = excitation cycles to settle before each DFT read.
    bool configureSweep(double startHz, double stepHz, uint16_t nPoints,
                        uint16_t settling = 15,
                        uint8_t range = AD5933_RANGE_2VPP,
                        uint8_t gain = AD5933_GAIN_X1);

    bool startSweep();                         // INIT_START -> START_SWEEP
    bool nextPoint(SweepPoint &out);           // read current point, then increment
    bool sweepComplete();                      // status sweep-done bit
    bool readTemperature(double &celsius);

    double clockHz() const { return _mclk; }
    double startHz() const { return _startHz; }
    double stepHz()  const { return _stepHz; }
    uint16_t points() const { return _nPoints; }

private:
    double   _mclk    = AD5933_INTERNAL_CLK_HZ;
    double   _startHz = 1000.0;
    double   _stepHz  = 1000.0;
    uint16_t _nPoints = 100;
    uint16_t _idx     = 0;
    uint8_t  _ctrlHigh = AD5933_CMD_NOP | AD5933_RANGE_2VPP | AD5933_GAIN_X1;

    bool writeReg(uint8_t reg, uint8_t val);
    bool readReg(uint8_t reg, uint8_t &val);
    bool write24(uint8_t reg, uint32_t code);
    bool write16(uint8_t reg, uint16_t val);
    bool read16(uint8_t reg, int16_t &val);
    bool issueCommand(uint8_t cmd);            // preserve range/gain, set command nibble
    bool waitStatus(uint8_t mask, uint32_t timeout_ms = 500);
};

#endif // AD5933_H
