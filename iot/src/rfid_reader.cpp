#include "rfid_reader.h"

#include <string.h>

#include <rfid_uid.h>

RfidReader::RfidReader(uint8_t ssPin,
                       uint8_t rstPin,
                       uint8_t sckPin,
                       uint8_t mosiPin,
                       uint8_t misoPin,
                       uint32_t rescanCooldownMs)
    : reader_(ssPin, rstPin),
      gate_(rescanCooldownMs),
      sckPin_(sckPin),
      mosiPin_(mosiPin),
      misoPin_(misoPin),
      ssPin_(ssPin),
      online_(false),
      lastRetryMs_(0) {}

bool RfidReader::begin() {
    // Start the bus with our custom pins first: MFRC522::PCD_Init() calls
    // SPI.begin() again, which is a no-op once the bus is running.
    SPI.begin(sckPin_, misoPin_, mosiPin_, ssPin_);
    reader_.PCD_Init();
    delay(10);

    const byte version = reader_.PCD_ReadRegister(MFRC522::VersionReg);
    online_ = (version != 0x00 && version != 0xFF);

    if (online_) {
        reader_.PCD_SetAntennaGain(MFRC522::RxGain_max);
        Serial.printf("[RFID] RC522 online (version 0x%02X)\n", version);
    } else {
        Serial.printf("[RFID] RC522 not detected (version 0x%02X) - check 3.3V + SPI pins\n", version);
    }
    return online_;
}

void RfidReader::maintain(uint32_t nowMs, uint32_t retryMs) {
    if (online_ || nowMs - lastRetryMs_ < retryMs) {
        return;
    }
    lastRetryMs_ = nowMs;
    begin();
}

bool RfidReader::poll(char *outUid, size_t outSize, uint32_t nowMs) {
    if (!online_) {
        return false;
    }

    char uid[16] = {0};
    bool hasCard = false;

    if (reader_.PICC_IsNewCardPresent() && reader_.PICC_ReadCardSerial()) {
        if (parking::uidBytesToHex(reader_.uid.uidByte, reader_.uid.size, uid, sizeof(uid)) > 0) {
            hasCard = true;
        }
        reader_.PICC_HaltA();
        reader_.PCD_StopCrypto1();
    }

    if (!gate_.update(hasCard ? uid : nullptr, nowMs)) {
        return false;
    }
    if (outSize < strlen(uid) + 1) {
        return false;
    }
    strncpy(outUid, uid, outSize - 1);
    outUid[outSize - 1] = '\0';
    return true;
}
