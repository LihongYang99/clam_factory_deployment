#pragma once
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>

namespace sen0709 {
constexpr uint8_t request[] = {1, 3, 0, 0, 0, 2, 0xC4, 0x0B};
struct Reading {
  float orp_mv;
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

inline void calibrationFrame(uint16_t point, uint16_t mv, uint8_t (&frame)[13]) {
  const uint8_t data[] = {1, 0x10, 1, 0x20, 0, 2, 4,
                         0, uint8_t(point), uint8_t(mv >> 8), uint8_t(mv), 0, 0};
  memcpy(frame, data, sizeof(data));
  const uint16_t crc = crc16(frame, 11);
  frame[11] = crc; frame[12] = crc >> 8;
}

inline const char* calibrationAck(const uint8_t* bytes, size_t size) {
  if (!size) return "TIMEOUT";
  if (size < 5) return "SHORT_FRAME";
  if (crc16(bytes, size-2) != (bytes[size-2] | uint16_t(bytes[size-1]) << 8))
    return "CRC_ERROR";
  if (bytes[0] != 1) return "WRONG_ADDRESS";
  if (size == 5 && bytes[1] == 0x90) return "MODBUS_EXCEPTION";
  const uint8_t expected[] = {1, 0x10, 1, 0x20, 0, 2};
  if (size != 8 || memcmp(bytes, expected, sizeof(expected))) return "UNEXPECTED_FRAME";
  return nullptr;
}

inline int32_t signedBE(const uint8_t* bytes) {
  const uint16_t raw = (uint16_t(bytes[0]) << 8) | bytes[1];
  return raw & 0x8000 ? int32_t(raw) - 65536 : raw;
}

// Only commit decoded values after the complete response passes validation.
inline const char* decode(const uint8_t* bytes, size_t size, Reading& out) {
  if (!size) return "TIMEOUT";
  if (size < 5) return "SHORT_FRAME";
  if (crc16(bytes, size - 2) != (bytes[size - 2] | uint16_t(bytes[size - 1]) << 8))
    return "CRC_ERROR";
  if (bytes[0] != 1) return "WRONG_ADDRESS";
  if (bytes[1] == 0x83 && size == 5) return "MODBUS_EXCEPTION";
  if (size != 9 || bytes[1] != 3 || bytes[2] != 4) return "UNEXPECTED_FRAME";
  Reading value{float(signedBE(bytes + 3)), signedBE(bytes + 5) / 10.0f};
  out = value;
  return nullptr;
}
}  // namespace sen0709
