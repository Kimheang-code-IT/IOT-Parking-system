#pragma once

#include <Arduino.h>
#include <MFRC522.h>
#include <SPI.h>

#include <scan_gate.h>

// RC522 RFID reader on remapped SPI pins (see parking_config.h).
// poll() returns each card presentation exactly once (ScanGate de-duplication).
class RfidReader {
public:
    RfidReader(uint8_t ssPin,
               uint8_t rstPin,
               uint8_t sckPin,
               uint8_t mosiPin,
               uint8_t misoPin,
               uint32_t rescanCooldownMs);

    // Initializes SPI + RC522. Returns false when the reader does not answer.
    bool begin();

    // Re-attempts begin() no more often than PARKING_RFID_RETRY_MS.
    void maintain(uint32_t nowMs, uint32_t retryMs);

    bool online() const { return online_; }

    // Fills outUid with e.g. "04A1B2C3" and returns true on a fresh scan.
    bool poll(char *outUid, size_t outSize, uint32_t nowMs);

private:
    MFRC522 reader_;
    parking::ScanGate gate_;
    uint8_t sckPin_;
    uint8_t mosiPin_;
    uint8_t misoPin_;
    uint8_t ssPin_;
    bool online_;
    uint32_t lastRetryMs_;
};
