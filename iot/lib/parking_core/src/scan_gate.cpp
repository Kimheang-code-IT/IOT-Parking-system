#include "scan_gate.h"

#include <string.h>

namespace parking {

ScanGate::ScanGate(uint32_t cooldownMs)
    : cooldownMs_(cooldownMs), lastAcceptedMs_(0), present_(false) {
    lastUid_[0] = '\0';
}

void ScanGate::setCooldownMs(uint32_t cooldownMs) {
    cooldownMs_ = cooldownMs;
}

uint32_t ScanGate::cooldownMs() const {
    return cooldownMs_;
}

bool ScanGate::update(const char *uid, uint32_t nowMs) {
    if (cooldownMs_ == 0) {
        cooldownMs_ = 1;
    }

    // No card on the reader — arm the gate for the next presentation.
    if (!uid || uid[0] == '\0') {
        present_ = false;
        lastUid_[0] = '\0';
        return false;
    }

    // First read of a card presentation.
    if (!present_) {
        present_ = true;
        strncpy(lastUid_, uid, sizeof(lastUid_) - 1);
        lastUid_[sizeof(lastUid_) - 1] = '\0';
        lastAcceptedMs_ = nowMs;
        return true;
    }

    // A different card was placed on the reader.
    if (strncmp(uid, lastUid_, sizeof(lastUid_)) != 0) {
        strncpy(lastUid_, uid, sizeof(lastUid_) - 1);
        lastUid_[sizeof(lastUid_) - 1] = '\0';
        lastAcceptedMs_ = nowMs;
        return true;
    }

    // Same card still held — allow re-report only after the cooldown.
    if (static_cast<uint32_t>(nowMs - lastAcceptedMs_) >= cooldownMs_) {
        lastAcceptedMs_ = nowMs;
        return true;
    }
    return false;
}

void ScanGate::reset() {
    present_ = false;
    lastUid_[0] = '\0';
    lastAcceptedMs_ = 0;
}

}  // namespace parking
