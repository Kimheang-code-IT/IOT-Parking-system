#pragma once

#include <Arduino.h>

// Non-blocking Wi-Fi connection manager with retry backoff.
class WifiManager {
public:
    WifiManager(const char *ssid, const char *password, uint32_t retryMs);

    void begin();
    void maintain(uint32_t nowMs);

    bool connected() const;
    const char *ssid() const { return ssid_; }

private:
    void startAttempt();

    const char *ssid_;
    const char *password_;
    uint32_t retryMs_;
    uint32_t lastAttemptMs_;
    bool started_;
};
