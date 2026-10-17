#include "gate_hardware.h"

#include <Wire.h>

#include "parking_config.h"

GateHardware::GateHardware(uint8_t servoPin,
                           uint8_t greenLedPin,
                           uint8_t redLedPin,
                           uint8_t lcdAddr,
                           uint8_t lcdCols,
                           uint8_t lcdRows,
                           uint8_t sdaPin,
                           uint8_t sclPin)
    : lcd_(lcdAddr, lcdCols, lcdRows),
      servoPin_(servoPin),
      greenLedPin_(greenLedPin),
      redLedPin_(redLedPin),
      sdaPin_(sdaPin),
      sclPin_(sclPin),
      gateOpen_(false),
      haveFrame_(false) {}

void GateHardware::begin() {
    pinMode(greenLedPin_, OUTPUT);
    pinMode(redLedPin_, OUTPUT);
    setLeds(false, true);

    Wire.begin(sdaPin_, sclPin_);
    lcd_.init();
    lcd_.backlight();
    lcd_.clear();

    servo_.setPeriodHertz(50);
    servo_.attach(servoPin_, PARKING_SERVO_MIN_US, PARKING_SERVO_MAX_US);
    closeGate();
}

void GateHardware::openGate() {
    servo_.write(PARKING_SERVO_OPEN_DEG);
    gateOpen_ = true;
    setLeds(true, false);
}

void GateHardware::closeGate() {
    servo_.write(PARKING_SERVO_CLOSED_DEG);
    gateOpen_ = false;
    setLeds(false, true);
}

void GateHardware::setLeds(bool green, bool red) {
    digitalWrite(greenLedPin_, green ? HIGH : LOW);
    digitalWrite(redLedPin_, red ? HIGH : LOW);
}

String GateHardware::fit16(const String &text) {
    if (text.length() >= PARKING_LCD_COLS) {
        return text.substring(0, PARKING_LCD_COLS);
    }
    String padded = text;
    while (padded.length() < PARKING_LCD_COLS) {
        padded += ' ';
    }
    return padded;
}

void GateHardware::showMessage(const String &line1, const String &line2) {
    const String l1 = fit16(line1);
    const String l2 = fit16(line2);
    if (haveFrame_ && l1 == lastLine1_ && l2 == lastLine2_) {
        return;
    }
    lastLine1_ = l1;
    lastLine2_ = l2;
    haveFrame_ = true;

    lcd_.setCursor(0, 0);
    lcd_.print(l1);
    lcd_.setCursor(0, 1);
    lcd_.print(l2);
}
