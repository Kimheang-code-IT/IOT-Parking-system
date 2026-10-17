#pragma once

#include <Arduino.h>
#include <ArduinoJson.h>
#include <HTTPClient.h>

// Outcome of an RFID scan request to the backend.
enum class ScanOutcome {
    Failed,           // network / server error
    Duplicate,        // backend de-duplication window
    Authorized,       // accepted, approval command queued
    PaymentPending,   // exit: fee due, pay then the command arrives
    Denied,           // unknown / blocked card, active session conflict, ...
};

struct ScanResult {
    ScanOutcome outcome = ScanOutcome::Failed;
    String message;
    String plateNumber;
    String sessionId;
    String invoiceId;
    String paymentStatus;
    String printSavedPath;
    bool hasAmount = false;
    float amount = 0.0f;
};

// A gate command polled from /api/iot/commands/next.
struct PendingCommand {
    bool hasCommand = false;
    String commandId;
    String command;  // ENTRY_APPROVED | EXIT_APPROVED | EXIT_DENIED
    String sessionId;
    String invoiceId;
    String plateNumber;
    String message;
    bool hasAmount = false;
    float amount = 0.0f;
};

// Authenticated HTTP client for the FastAPI backend.
// Every request carries x-device-code / x-device-token (task device auth).
class ParkingApiClient {
public:
    ParkingApiClient(const char *baseUrl, const char *deviceCode, const char *deviceToken);

    ScanResult entryScan(const char *cardUid);
    ScanResult exitScan(const char *cardUid);

    bool pollCommand(PendingCommand &out);
    bool ackCommand(const String &commandId, bool success, const String &detail);
    bool reportGateEvent(const char *event, const String &sessionId, const String &commandId, const String &detail);
    bool heartbeat();

    const String &lastError() const { return lastError_; }

private:
    bool request(const char *method, const String &path, const String &body, String &response, int &statusCode);
    ScanResult parseScanResponse(int statusCode, const String &response);
    String url(const String &path) const;

    String baseUrl_;
    String deviceCode_;
    String deviceToken_;
    String lastError_;
};
