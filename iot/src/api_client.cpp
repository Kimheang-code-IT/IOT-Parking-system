#include "api_client.h"

#include <WiFi.h>

#include "parking_config.h"

ParkingApiClient::ParkingApiClient(const char *baseUrl, const char *deviceCode, const char *deviceToken)
    : baseUrl_(baseUrl), deviceCode_(deviceCode), deviceToken_(deviceToken) {}

String ParkingApiClient::url(const String &path) const {
    if (path.startsWith("http")) {
        return path;
    }
    String base = baseUrl_;
    if (base.endsWith("/")) {
        base.remove(base.length() - 1);
    }
    return base + path;
}

bool ParkingApiClient::request(const char *method, const String &path, const String &body, String &response, int &statusCode) {
    lastError_ = "";
    statusCode = 0;

    WiFiClient client;
    HTTPClient http;
    http.setTimeout(PARKING_HTTP_TIMEOUT_MS);
    http.setConnectTimeout(PARKING_HTTP_TIMEOUT_MS);

    if (!http.begin(client, url(path))) {
        lastError_ = "HTTP begin failed";
        return false;
    }
    http.addHeader("Content-Type", "application/json");
    http.addHeader("x-device-code", deviceCode_);
    http.addHeader("x-device-token", deviceToken_);

    if (strcmp(method, "GET") == 0) {
        statusCode = http.GET();
    } else {
        statusCode = http.POST(body);
    }

    if (statusCode > 0) {
        response = http.getString();
    } else {
        lastError_ = http.errorToString(statusCode);
    }
    http.end();
    return statusCode > 0;
}

ScanResult ParkingApiClient::parseScanResponse(int statusCode, const String &response) {
    ScanResult result;
    JsonDocument doc;
    const DeserializationError err = deserializeJson(doc, response);

    if (!err) {
        result.message = doc["message"] | "";
        result.plateNumber = doc["plateNumber"] | "";
        result.sessionId = doc["sessionId"] | "";
        result.invoiceId = doc["invoiceId"] | "";
        result.paymentStatus = doc["paymentStatus"] | "";
        result.printSavedPath = doc["printSavedPath"] | "";
        if (doc["amount"].is<float>() || doc["amount"].is<int>()) {
            result.amount = doc["amount"].as<float>();
            result.hasAmount = true;
        }
    }

    if (statusCode == 401 || statusCode == 403 || statusCode >= 500) {
        result.outcome = ScanOutcome::Failed;
        if (result.message.isEmpty()) {
            result.message = statusCode == 401 ? "Device token rejected" : "Server error";
        }
        return result;
    }

    if (statusCode == 200 && !err) {
        if (doc["duplicate"] | false) {
            result.outcome = ScanOutcome::Duplicate;
        } else if (doc["authorized"] | false) {
            result.outcome = ScanOutcome::Authorized;
        } else if (doc["paymentPending"] | false) {
            result.outcome = ScanOutcome::PaymentPending;
        } else {
            result.outcome = ScanOutcome::Denied;
        }
        return result;
    }

    result.outcome = ScanOutcome::Denied;
    if (result.message.isEmpty()) {
        result.message = statusCode > 0 ? String("HTTP ") + statusCode : lastError_;
    }
    return result;
}

ScanResult ParkingApiClient::entryScan(const char *cardUid) {
    JsonDocument doc;
    doc["deviceCode"] = deviceCode_;
    doc["cardUid"] = cardUid;
    String body;
    serializeJson(doc, body);

    String response;
    int statusCode = 0;
    if (!request("POST", "/api/rfid/entry-scan", body, response, statusCode)) {
        ScanResult failed;
        failed.outcome = ScanOutcome::Failed;
        failed.message = lastError_;
        return failed;
    }
    return parseScanResponse(statusCode, response);
}

ScanResult ParkingApiClient::exitScan(const char *cardUid) {
    JsonDocument doc;
    doc["deviceCode"] = deviceCode_;
    doc["cardUid"] = cardUid;
    String body;
    serializeJson(doc, body);

    String response;
    int statusCode = 0;
    if (!request("POST", "/api/rfid/exit-scan", body, response, statusCode)) {
        ScanResult failed;
        failed.outcome = ScanOutcome::Failed;
        failed.message = lastError_;
        return failed;
    }
    return parseScanResponse(statusCode, response);
}

bool ParkingApiClient::pollCommand(PendingCommand &out) {
    out = PendingCommand();
    const String path = String("/api/iot/commands/next?deviceCode=") + deviceCode_;

    String response;
    int statusCode = 0;
    if (!request("GET", path, "", response, statusCode) || statusCode != 200) {
        return false;
    }

    JsonDocument doc;
    if (deserializeJson(doc, response) || doc.isNull() || !doc["commandId"].is<String>()) {
        return false;
    }

    out.hasCommand = true;
    out.commandId = doc["commandId"] | "";
    out.command = doc["command"] | "";
    out.message = doc["message"] | "";
    JsonObject payload = doc["payload"].as<JsonObject>();
    if (!payload.isNull()) {
        out.sessionId = payload["sessionId"] | "";
        out.invoiceId = payload["invoiceId"] | "";
        out.plateNumber = payload["plateNumber"] | "";
        if (payload["amount"].is<float>() || payload["amount"].is<int>()) {
            out.amount = payload["amount"].as<float>();
            out.hasAmount = true;
        }
    }
    return true;
}

bool ParkingApiClient::ackCommand(const String &commandId, bool success, const String &detail) {
    JsonDocument doc;
    doc["deviceCode"] = deviceCode_;
    doc["commandId"] = commandId;
    doc["status"] = success ? "completed" : "failed";
    if (!detail.isEmpty()) {
        doc["detail"] = detail;
    }
    String body;
    serializeJson(doc, body);

    String response;
    int statusCode = 0;
    return request("POST", "/api/iot/commands/ack", body, response, statusCode) && statusCode == 200;
}

bool ParkingApiClient::reportGateEvent(const char *event,
                                       const String &sessionId,
                                       const String &commandId,
                                       const String &detail) {
    JsonDocument doc;
    doc["deviceCode"] = deviceCode_;
    doc["event"] = event;
    if (!sessionId.isEmpty()) {
        doc["sessionId"] = sessionId;
    }
    if (!commandId.isEmpty()) {
        doc["commandId"] = commandId;
    }
    if (!detail.isEmpty()) {
        doc["detail"] = detail;
    }
    String body;
    serializeJson(doc, body);

    String response;
    int statusCode = 0;
    return request("POST", "/api/iot/gate/event", body, response, statusCode) && statusCode == 200;
}

bool ParkingApiClient::heartbeat() {
    JsonDocument doc;
    doc["deviceCode"] = deviceCode_;
    String body;
    serializeJson(doc, body);

    String response;
    int statusCode = 0;
    return request("POST", "/api/iot/heartbeat", body, response, statusCode) && statusCode == 200;
}
