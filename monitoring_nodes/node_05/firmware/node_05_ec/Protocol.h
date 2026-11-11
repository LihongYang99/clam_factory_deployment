#pragma once
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <cctype>

namespace ezoec {

// Atlas UART replies are CR-delimited ASCII: optional data followed by *OK.
struct Reply {
  uint8_t raw[128]{};
  size_t count = 0;
  char line[64]{};
  size_t length = 0;
  char data[64]{};
  bool hasData = false;
  bool done = false;
  bool truncated = false;
  const char* error = nullptr;

  void fail(const char* reason) { error = reason; done = true; }

  void push(uint8_t byte) {
    if (done) return;
    if (count == sizeof(raw)) {
      truncated = true;
      fail("FRAME_OVERFLOW");
      return;
    }
    raw[count++] = byte;
    if (byte == '\n') return;
    if (byte == '\r') {
      if (!length) return;
      line[length] = '\0';
      if (!strcmp(line, "*OK")) done = true;
      else if (line[0] == '*') {
        fail(!strcmp(line, "*RS") ? "SENSOR_RESET" : "SENSOR_ERROR");
      } else if (hasData) fail("UNEXPECTED_FRAME");
      else { strcpy(data, line); hasData = true; }
      length = 0;
    } else if (byte < 32 || byte > 126) fail("INVALID_ASCII");
    else if (length == sizeof(line) - 1) fail("LINE_OVERFLOW");
    else line[length++] = char(byte);
  }

  const char* result(bool needsData) const {
    if (error) return error;
    if (!done) return "TIMEOUT";
    if (hasData != needsData) return "UNEXPECTED_FRAME";
    return nullptr;
  }
};

inline bool startsWith(const char* value, const char* prefix) {
  while (*prefix) {
    if (toupper(static_cast<unsigned char>(*value++)) !=
        toupper(static_cast<unsigned char>(*prefix++))) return false;
  }
  return true;
}

inline bool decimal(const char* text, double& value) {
  // Reject partial parses, NaN/Inf, and multi-output comma-separated readings.
  if (!*text) return false;
  bool digit = false;
  bool dot = false;
  const char* p = text;
  if (*p == '+' || *p == '-') ++p;
  for (; *p; ++p) {
    if (*p >= '0' && *p <= '9') digit = true;
    else if (*p == '.' && !dot) dot = true;
    else return false;
  }
  if (!digit) return false;
  value = strtod(text, nullptr);
  return std::isfinite(value);
}

inline bool setting(const char* data, const char* prefix, double& value) {
  return startsWith(data, prefix) && decimal(data + strlen(prefix), value);
}

inline const char* conductivity(const char* data, double& value) {
  if (!decimal(data, value) || value < 0) return "INVALID_READING";
  // K10 probe upper range: 1 S/cm (Atlas EZO-EC datasheet V6.7, p. 3).
  if (value > 1000000) return "OUT_OF_RANGE";
  return nullptr;
}

}  // namespace ezoec
