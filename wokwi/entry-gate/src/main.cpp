/**
 * Wokwi Entry Gate — simulates LPR + calls POST /api/iot/entry-scan
 *
 * Setup:
 * 1. Run FastAPI on your PC: uvicorn app.main:app --host 0.0.0.0 --port 8000
 * 2. Set API_HOST to your PC LAN IP (ipconfig), NOT localhost
 * 3. Open this folder in Wokwi (VS Code extension) and Start Simulation
 * 4. Press the green button = vehicle entry with plate WK-SIM01
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// --- CHANGE to your computer's LAN IP (same WiFi as Wokwi gateway) ---
#define API_HOST "192.168.0.100"
#define API_PORT 8000

#define DEVICE_CODE "ENTRY_GATE_01"
#define DEVICE_TOKEN "secret-entry-token"
#define SIM_PLATE "WK-SIM01"

#define BTN_PIN 27
#define LED_OK 25
#define LED_ERR 26

const char *WIFI_SSID = "Wokwi-GUEST";
const char *WIFI_PASS = "";

bool lastBtn = HIGH;

void blinkLed(int pin, int times) {
  for (int i = 0; i < times; i++) {
    digitalWrite(pin, HIGH);
    delay(120);
    digitalWrite(pin, LOW);
    delay(120);
  }
}

bool postEntryScan() {
  String url = String("http://") + API_HOST + ":" + String(API_PORT) + "/api/iot/entry-scan";

  StaticJsonDocument<256> doc;
  doc["deviceCode"] = DEVICE_CODE;
  doc["licensePlate"] = SIM_PLATE;
  doc["vehicleType"] = "Car";
  doc["vehicleDescription"] = "Wokwi Simulator";

  String body;
  serializeJson(doc, body);

  HTTPClient http;
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("x-device-code", DEVICE_CODE);
  http.addHeader("x-device-token", DEVICE_TOKEN);

  Serial.println("[HTTP] POST entry-scan");
  Serial.println(body);

  int code = http.POST(body);
  String response = http.getString();
  http.end();

  Serial.printf("[HTTP] Status: %d\n", code);
  Serial.println(response);

  return code >= 200 && code < 300;
}

void setup() {
  Serial.begin(115200);
  pinMode(BTN_PIN, INPUT_PULLUP);
  pinMode(LED_OK, OUTPUT);
  pinMode(LED_ERR, OUTPUT);

  Serial.println("\n=== IOT Parking Entry Gate (Wokwi) ===");
  Serial.printf("API: http://%s:%d\n", API_HOST, API_PORT);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("WiFi connecting");
  int tries = 0;
  while (WiFi.status() != WL_CONNECTED && tries < 40) {
    delay(500);
    Serial.print(".");
    tries++;
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("WiFi OK: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("WiFi failed — Wokwi-GUEST network required in simulator");
  }
}

void loop() {
  bool btn = digitalRead(BTN_PIN);
  if (lastBtn == HIGH && btn == LOW) {
    delay(30);
    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("No WiFi");
      blinkLed(LED_ERR, 3);
    } else if (postEntryScan()) {
      blinkLed(LED_OK, 2);
    } else {
      blinkLed(LED_ERR, 5);
    }
  }
  lastBtn = btn;
  delay(20);
}
