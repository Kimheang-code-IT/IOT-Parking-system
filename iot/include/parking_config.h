#pragma once

// ---------------------------------------------------------------------------
// Smart IoT Parking — shared firmware configuration (both gate roles).
//
// Pin map (non-conflicting):
//   Existing wiring kept:
//     TRIG_PIN 5, ECHO_PIN 18      HC-SR04 vehicle presence (approach)
//     SERVO_PIN 13                 gate servo
//     GREEN_LED 25, RED_LED 26     gate state LEDs
//     LCD I2C SDA 21, SCL 22       16x2 LCD
//   New:
//     RC522 RFID (SPI remapped to avoid 5/18):
//       SS 4, RST 27, SCK 14, MOSI 23, MISO 19
//     Passage safety sensor (second HC-SR04 under the gate):
//       TRIG 32, ECHO 33
// ---------------------------------------------------------------------------

#include <Arduino.h>

// Gate role — provided by platformio.ini build flags:
//   1 = entry gate, 2 = exit gate
#ifndef PARKING_GATE_ROLE
#define PARKING_GATE_ROLE 1
#endif
#define PARKING_ROLE_ENTRY 1
#define PARKING_ROLE_EXIT 2

#if PARKING_GATE_ROLE == PARKING_ROLE_EXIT
#define PARKING_IS_EXIT_GATE 1
#else
#define PARKING_IS_EXIT_GATE 0
#endif

// Optional secrets file (git-ignored). Copy parking_secrets.example.h first.
#if defined(__has_include)
#if __has_include("parking_secrets.h")
#include "parking_secrets.h"
#endif
#endif

// ---------------------------------------------------------------- Wi-Fi / API
#ifndef PARKING_WIFI_SSID
#define PARKING_WIFI_SSID ""            // set in include/parking_secrets.h
#endif
#ifndef PARKING_WIFI_PASSWORD
#define PARKING_WIFI_PASSWORD ""
#endif
#ifndef PARKING_API_BASE_URL
#define PARKING_API_BASE_URL "http://192.168.1.100:8000"  // LAN IP of the FastAPI PC
#endif

// Device identity + token (must match .env IOT_*_DEVICE_TOKEN on the backend)
#ifndef PARKING_ENTRY_DEVICE_TOKEN
#define PARKING_ENTRY_DEVICE_TOKEN "secret-entry-token"
#endif
#ifndef PARKING_EXIT_DEVICE_TOKEN
#define PARKING_EXIT_DEVICE_TOKEN "secret-exit-token"
#endif

#if PARKING_IS_EXIT_GATE
#define PARKING_DEVICE_CODE "EXIT_GATE_01"
#define PARKING_DEVICE_TOKEN PARKING_EXIT_DEVICE_TOKEN
#else
#define PARKING_DEVICE_CODE "ENTRY_GATE_01"
#define PARKING_DEVICE_TOKEN PARKING_ENTRY_DEVICE_TOKEN
#endif

// Oldest wiring (kept exactly as the original sketch)
#define PARKING_TRIG_PIN 5
#define PARKING_ECHO_PIN 18
#define PARKING_SERVO_PIN 13
#define PARKING_GREEN_LED_PIN 25
#define PARKING_RED_LED_PIN 26

#define PARKING_LCD_I2C_ADDR 0x27
#define PARKING_LCD_COLS 16
#define PARKING_LCD_ROWS 2
#define PARKING_I2C_SDA_PIN 21
#define PARKING_I2C_SCL_PIN 22

// RC522 RFID reader (SPI remapped — see pin map above)
#define PARKING_RFID_SS_PIN 4
#define PARKING_RFID_RST_PIN 27
#define PARKING_RFID_SCK_PIN 14
#define PARKING_RFID_MOSI_PIN 23
#define PARKING_RFID_MISO_PIN 19

// Passage safety sensor (under the gate) — set to 0 if not wired yet.
// With the sensor disabled the gate closes when the approach sensor clears;
// with it enabled the gate never closes while the passage is blocked/faulty.
#define PARKING_PASSAGE_SENSOR_ENABLED 1
#define PARKING_PASSAGE_TRIG_PIN 32
#define PARKING_PASSAGE_ECHO_PIN 33

// ---------------------------------------------------------------- Behaviour
#define PARKING_PRESENCE_CM 20.0f          // car detected within this distance
#define PARKING_PRESENCE_CLEAR_CM 30.0f    // car considered gone beyond this
#define PARKING_PASSAGE_CM 25.0f           // obstruction inside the passage
#define PARKING_SENSOR_INTERVAL_MS 150
#define PARKING_SENSOR_FAULT_READS 5       // consecutive bad reads -> sensor fault
#define PARKING_RFID_RESCAN_COOLDOWN_MS 8000
#define PARKING_CMD_POLL_INTERVAL_MS 2000
#define PARKING_HEARTBEAT_INTERVAL_MS 30000
#define PARKING_WIFI_RETRY_MS 5000
#define PARKING_HTTP_TIMEOUT_MS 4000
#define PARKING_RFID_RETRY_MS 5000

// Gate flow timings (see lib/parking_core/src/gate_flow.h)
#define PARKING_AUTH_TIMEOUT_MS 15000      // scan -> approval command wait
#define PARKING_DENIAL_HOLD_MS 4000
#define PARKING_PASS_TIMEOUT_MS 20000      // open too long without car passing
#define PARKING_MIN_OPEN_MS 1500
#define PARKING_PAYMENT_TIMEOUT_MS 300000  // exit: fee waiting at the gate
#define PARKING_PAYMENT_ABSENCE_GRACE_MS 10000
#define PARKING_COMMAND_VALIDITY_MS 180000 // keep in sync with backend GATE_COMMAND_TIMEOUT_SECONDS

#define PARKING_SERVO_OPEN_DEG 90
#define PARKING_SERVO_CLOSED_DEG 0
#define PARKING_SERVO_MIN_US 500
#define PARKING_SERVO_MAX_US 2400
