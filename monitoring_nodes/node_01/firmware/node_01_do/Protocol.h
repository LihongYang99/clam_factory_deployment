#pragma once
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>

namespace sen0681 {
constexpr uint8_t request[] = {1, 3, 0, 0, 0, 6, 0xC5, 0xC8};
struct Reading {
  float saturation_pct;
  float do_mg_l;
  float temperature_c;
};

inline uint16_t crc16(const uint8_t* bytes, size_t size) {
  uint16_t crc = 0xFFFF;
  for (size_t i = 0; i < size; ++i) {
    crc ^= bytes[i];
    for (int bit = 0; bit < 8; ++bit)
      crc = (crc & 1) ? (crc >> 1) ^ 0xA001 : crc >> 1;
  }
  return crc;
}

inline float floatBE(const uint8_t* bytes) {
  static_assert(sizeof(float) == 4, "SEN0681 requires float32");
  const uint32_t bits = (uint32_t(bytes[0]) << 24) |
      (uint32_t(bytes[1]) << 16) | (uint32_t(bytes[2]) << 8) | bytes[3];
  float value;
  memcpy(&value, &bits, sizeof(value));
  return value;
}

// Only commit decoded values after the complete response passes validation.
inline const char* decode(const uint8_t* bytes, size_t size, Reading& out) {
  if (!size) return "TIMEOUT";
  if (size < 5) return "SHORT_FRAME";
  if (crc16(bytes, size - 2) != (bytes[size - 2] | uint16_t(bytes[size - 1]) << 8))
    return "CRC_ERROR";
  if (bytes[0] != 1) return "WRONG_ADDRESS";
  if (bytes[1] == 0x83 && size == 5) return "MODBUS_EXCEPTION";
  if (size != 17 || bytes[1] != 3 || bytes[2] != 12) return "UNEXPECTED_FRAME";
  Reading value{floatBE(bytes + 3) * 100.0f, floatBE(bytes + 7), floatBE(bytes + 11)};
  if (!std::isfinite(value.saturation_pct) || !std::isfinite(value.do_mg_l) ||
      !std::isfinite(value.temperature_c)) return "NON_FINITE";
  if (value.saturation_pct < 0 || value.saturation_pct > 200 ||
      value.do_mg_l < 0 || value.do_mg_l > 20 ||
      value.temperature_c < 0 || value.temperature_c > 40) return "OUT_OF_RANGE";
  out = value;
  return nullptr;
}
}  // namespace sen0681
