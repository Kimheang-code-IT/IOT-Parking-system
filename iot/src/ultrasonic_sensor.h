#pragma once

#include <Arduino.h>

// HC-SR04 ultrasonic distance sensor (used for both the approach detector
// and the passage safety sensor).
class UltrasonicSensor {
public:
    UltrasonicSensor(uint8_t trigPin, uint8_t echoPin);

    void begin();

    // Returns false when no echo was received (sensor missing / out of range).
    bool readCm(float &distanceCm);

private:
    uint8_t trigPin_;
    uint8_t echoPin_;
};
