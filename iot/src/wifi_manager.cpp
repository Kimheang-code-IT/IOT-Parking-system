#include "wifi_manager.h"

#include <WiFi.h>

WifiManager::WifiManager(const char *ssid, const char *password, uint32_t retryMs)
    : ssid_(ssid), password_(password), retryMs_(retryMs), lastAttemptMs_(0), started_(false) {}

void WifiManager::begin() {
    WiFi.mode(WIFI_STA);
    WiFi.setAutoReconnect(true);
    startAttempt();
}

void WifiManager::startAttempt() {
    if (!ssid_ || ssid_[0] == '\0') {
        return;  // secrets not configured yet
    }
    Serial.printf("[WiFi] Connecting to %s ...\n", ssid_);
    WiFi.begin(ssid_, password_);
    started_ = true;
}

void WifiManager::maintain(uint32_t nowMs) {
    if (started_ && WiFi.status() == WL_CONNECTED) {
        return;
    }
    if (nowMs - lastAttemptMs_ < retryMs_) {
        return;
    }
    lastAttemptMs_ = nowMs;
    if (started_) {
        WiFi.disconnect();
    }
    startAttempt();
}

bool WifiManager::connected() const {
    return WiFi.status() == WL_CONNECTED;
}
