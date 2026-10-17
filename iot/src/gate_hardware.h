#pragma once

#include <Arduino.h>
#include <LiquidCrystal_I2C.h>
#include <ESP32Servo.h>

// Gate hardware bundle: servo, status LEDs and the 16x2 I2C LCD.
// LCD writes are cached to avoid flicker between identical frames.
class GateHardware {
public:
    GateHardware(uint8_t servoPin,
                 uint8_t greenLedPin,
                 uint8_t redLedPin,
                 uint8_t lcdAddr,
                 uint8_t lcdCols,
                 uint8_t lcdRows,
                 uint8_t sdaPin,
                 uint8_t sclPin);

    void begin();
    void openGate();
    void closeGate();
    bool gateOpen() const { return gateOpen_; }

    void setLeds(bool green, bool red);

    // Shows two 16-char lines; no-op when the frame is unchanged.
    void showMessage(const String &line1, const String &line2);

private:
    static String fit16(const String &text);

    Servo servo_;
    LiquidCrystal_I2C lcd_;
    uint8_t servoPin_;
    uint8_t greenLedPin_;
    uint8_t redLedPin_;
    uint8_t sdaPin_;
    uint8_t sclPin_;
    bool gateOpen_;
    bool haveFrame_;
    String lastLine1_;
    String lastLine2_;
};
