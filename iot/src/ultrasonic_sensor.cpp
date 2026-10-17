#include "ultrasonic_sensor.h"

UltrasonicSensor::UltrasonicSensor(uint8_t trigPin, uint8_t echoPin)
    : trigPin_(trigPin), echoPin_(echoPin) {}

void UltrasonicSensor::begin() {
    pinMode(trigPin_, OUTPUT);
    pinMode(echoPin_, INPUT);
    digitalWrite(trigPin_, LOW);
}

bool UltrasonicSensor::readCm(float &distanceCm) {
    digitalWrite(trigPin_, LOW);
    delayMicroseconds(2);
    digitalWrite(trigPin_, HIGH);
    delayMicroseconds(10);
    digitalWrite(trigPin_, LOW);

    const unsigned long duration = pulseIn(echoPin_, HIGH, 30000UL);
    if (duration == 0) {
        return false;
    }
    distanceCm = duration * 0.0343f / 2.0f;
    return true;
}
