#pragma once

// ---------------------------------------------------------------------------
// Copy this file to include/parking_secrets.h and fill in your values.
// parking_secrets.h is git-ignored so real credentials never get committed.
//
//   copy parking_secrets.example.h parking_secrets.h
//
// BUILD ORDER: platformio.ini picks the role:
//   entry_gate env -> ENTRY role -> device ENTRY_GATE_01 + entry token
//   exit_gate  env -> EXIT  role -> device EXIT_GATE_01  + exit token
// ---------------------------------------------------------------------------

// Wi-Fi the ESP32 connects to (must reach the PC running FastAPI)
#define PARKING_WIFI_SSID "YOUR_WIFI_NAME"
#define PARKING_WIFI_PASSWORD "YOUR_WIFI_PASSWORD"

// FastAPI base URL — LAN IP of the PC running uvicorn, port 8000.
// Example: uvicorn app.main:app --host 0.0.0.0 --port 8000
// Do NOT use localhost here: from the ESP32 that means the ESP32 itself.
#define PARKING_API_BASE_URL "http://192.168.1.100:8000"

// Device tokens — must match backend/.env
//   IOT_ENTRY_DEVICE_TOKEN / IOT_EXIT_DEVICE_TOKEN
#define PARKING_ENTRY_DEVICE_TOKEN "secret-entry-token"
#define PARKING_EXIT_DEVICE_TOKEN "secret-exit-token"
