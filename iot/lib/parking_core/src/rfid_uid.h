#pragma once

#include <stddef.h>
#include <stdint.h>

namespace parking {

// Formats UID bytes as uppercase hex without separators (e.g. "04A1B2C3").
// Returns the number of characters written (not counting the terminator) or 0.
size_t uidBytesToHex(const uint8_t *bytes, size_t length, char *out, size_t outSize);

// Normalizes a raw UID string: strips ':', '-', ' ' and tabs, uppercases hex.
// Returns the normalized length (8..14, even) or 0 when invalid.
size_t normalizeUid(const char *raw, char *out, size_t outSize);

// True when the string is an even-length run of 8..14 hex characters.
bool isValidUid(const char *normalized);

}  // namespace parking
