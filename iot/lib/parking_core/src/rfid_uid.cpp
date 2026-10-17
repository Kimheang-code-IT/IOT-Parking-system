#include "rfid_uid.h"

namespace parking {

static bool isHexDigit(char c) {
    return (c >= '0' && c <= '9') || (c >= 'A' && c <= 'F') || (c >= 'a' && c <= 'f');
}

static char upperHex(char c) {
    return (c >= 'a' && c <= 'f') ? static_cast<char>(c - 'a' + 'A') : c;
}

size_t uidBytesToHex(const uint8_t *bytes, size_t length, char *out, size_t outSize) {
    static const char *kHex = "0123456789ABCDEF";
    if (!bytes || !out || length == 0 || length > 15) {
        return 0;
    }
    if (outSize < length * 2 + 1) {
        return 0;
    }
    for (size_t i = 0; i < length; ++i) {
        out[i * 2] = kHex[(bytes[i] >> 4) & 0x0F];
        out[i * 2 + 1] = kHex[bytes[i] & 0x0F];
    }
    out[length * 2] = '\0';
    return length * 2;
}

size_t normalizeUid(const char *raw, char *out, size_t outSize) {
    if (!raw || !out || outSize == 0) {
        return 0;
    }
    char buffer[32];
    size_t n = 0;
    for (const char *p = raw; *p != '\0'; ++p) {
        const char c = *p;
        if (c == ':' || c == '-' || c == ' ' || c == '\t') {
            continue;
        }
        if (!isHexDigit(c)) {
            return 0;
        }
        if (n >= sizeof(buffer)) {
            return 0;
        }
        buffer[n++] = upperHex(c);
    }
    if (n < 8 || n > 14 || (n % 2) != 0 || n + 1 > outSize) {
        return 0;
    }
    for (size_t i = 0; i < n; ++i) {
        out[i] = buffer[i];
    }
    out[n] = '\0';
    return n;
}

bool isValidUid(const char *normalized) {
    if (!normalized) {
        return false;
    }
    size_t n = 0;
    for (const char *p = normalized; *p != '\0'; ++p) {
        if (!isHexDigit(*p)) {
            return false;
        }
        ++n;
    }
    return n >= 8 && n <= 14 && (n % 2) == 0;
}

}  // namespace parking
