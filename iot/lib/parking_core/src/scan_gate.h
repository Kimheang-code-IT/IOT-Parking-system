#pragma once

#include <stdint.h>

namespace parking {

// Suppresses duplicate reads of the same RFID card.
//
// Feed update() with the UID currently on the reader (nullptr/"" when none).
// It returns true exactly once per card presentation, so:
//   - removing and re-presenting the card reports again
//   - placing a different card reports immediately
//   - holding the same card reports again only after the cooldown window
class ScanGate {
public:
    explicit ScanGate(uint32_t cooldownMs);

    void setCooldownMs(uint32_t cooldownMs);
    uint32_t cooldownMs() const;

    bool update(const char *uid, uint32_t nowMs);
    void reset();

private:
    char lastUid_[16];
    uint32_t cooldownMs_;
    uint32_t lastAcceptedMs_;
    bool present_;
};

}  // namespace parking
