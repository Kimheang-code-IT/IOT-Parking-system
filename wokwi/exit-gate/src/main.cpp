/**
 * Wokwi Exit Gate — exit-verify → payment webhook → open-gate
 *
 * Edit INVOICE_ID / PLATE after an entry scan from entry-gate simulator.
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

#define API_HOST "192.168.0.100"
#define API_PORT 8000
#define WEBHOOK_SECRET "change-me-webhook-secret"

#define DEVICE_CODE "EXIT_GATE_01"
#define DEVICE_TOKEN "secret-exit-token"

// Update these from entry-scan Serial output / dashboard
#define INVOICE_ID "IN-000002"
#define PLATE "WK-SIM01"

#define BTN_PIN 27
#define LED_GATE 25

const char *WIFI_SSID = "Wokwi-GUEST";
const char *WIFI_PASS = "";

bool lastBtn = HIGH;

String httpPost(const char *path, const String &body, bool iotHeaders, bool webhook = false) {
  String url = String("http://") + API_HOST + ":" + String(API_PORT) + path;
  HTTPClient http;
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  if (iotHeaders) {
    http.addHeader("x-device-code", DEVICE_CODE);
    http.addHeader("x-device-token", DEVICE_TOKEN);
  }
  if (webhook) {
    http.addHeader("x-webhook-secret", WEBHOOK_SECRET);
  }
  int code = http.POST(body);
  String res = http.getString();
  http.end();
  Serial.printf("POST %s -> %d\n", path, code);
  Serial.println(res);
  return res;
}

void runExitFlow() {
  StaticJsonDocument<256> exitDoc;
  exitDoc["deviceCode"] = DEVICE_CODE;
  exitDoc["invoiceId"] = INVOICE_ID;
  exitDoc["licensePlate"] = PLATE;
  String exitBody;
  serializeJson(exitDoc, exitBody);

  String exitRes = httpPost("/api/iot/exit-verify", exitBody, true);
  StaticJsonDocument<512> parsed;
  if (deserializeJson(parsed, exitRes)) {
    Serial.println("Bad exit JSON");
    return;
  }
  if (!parsed["success"].as<bool>()) {
    Serial.println("Exit verify failed");
    return;
  }

  float amount = parsed["amount"] | 1.0f;
  const char *sessionId = parsed["sessionId"];

  StaticJsonDocument<256> payDoc;
  payDoc["invoiceId"] = INVOICE_ID;
  payDoc["amount"] = amount;
  payDoc["paymentMethod"] = "KHQR";
  payDoc["success"] = true;
  String payBody;
  serializeJson(payDoc, payBody);
  httpPost("/api/payment/webhook", payBody, false, true);

  StaticJsonDocument<128> gateDoc;
  gateDoc["deviceCode"] = DEVICE_CODE;
  gateDoc["sessionId"] = sessionId;
  String gateBody;
  serializeJson(gateDoc, gateBody);
  httpPost("/api/iot/open-gate", gateBody, true);

  digitalWrite(LED_GATE, HIGH);
  delay(2000);
  digitalWrite(LED_GATE, LOW);
}

void setup() {
  Serial.begin(115200);
  pinMode(BTN_PIN, INPUT_PULLUP);
  pinMode(LED_GATE, OUTPUT);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nExit gate ready. Press button for full exit flow.");
}

void loop() {
  bool btn = digitalRead(BTN_PIN);
  if (lastBtn == HIGH && btn == LOW) {
    runExitFlow();
  }
  lastBtn = btn;
  delay(20);
}
