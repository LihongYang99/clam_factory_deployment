#include "../firmware/node_01_do/Protocol.h"
#include <cassert>
#include <cstdio>

void updateCRC(uint8_t* bytes, size_t size) {
  const uint16_t crc = sen0681::crc16(bytes, size - 2);
  bytes[size - 2] = crc & 0xFF;
  bytes[size - 1] = crc >> 8;
}

int main() {
  using namespace sen0681;
  assert(crc16(request, 6) == 0xC8C5);
  // Manufacturer response example: 91.7653%, 7.071373 mg/L, 28.690317 C.
  uint8_t frame[] = {1,3,12,0x3F,0x6A,0xEB,0x52,0x40,0xE2,0x48,0xB0,
                      0x41,0xE5,0x85,0xC5,0xA7,0x49};
  Reading result{};
  assert(!decode(frame, sizeof(frame), result));
  assert(std::fabs(result.do_mg_l - 7.071373f) < 0.00001f);
  assert(std::fabs(result.saturation_pct - 91.7653f) < 0.0001f);
  assert(std::fabs(result.temperature_c - 28.690317f) < 0.00001f);
  const float previous = result.do_mg_l;
  assert(!strcmp(decode(frame, 0, result), "TIMEOUT"));
  assert(!strcmp(decode(frame, 3, result), "SHORT_FRAME"));
  frame[7] ^= 1;
  assert(!strcmp(decode(frame, sizeof(frame), result), "CRC_ERROR"));
  assert(result.do_mg_l == previous);
  frame[7] ^= 1;
  frame[0] = 2;
  updateCRC(frame, sizeof(frame));
  assert(!strcmp(decode(frame, sizeof(frame), result), "WRONG_ADDRESS"));
  frame[0] = 1;
  frame[2] = 10;
  updateCRC(frame, sizeof(frame));
  assert(!strcmp(decode(frame, sizeof(frame), result), "UNEXPECTED_FRAME"));
  frame[2] = 12;
  frame[7] = 0x7F; frame[8] = 0xC0; frame[9] = 0; frame[10] = 0;
  updateCRC(frame, sizeof(frame));
  assert(!strcmp(decode(frame, sizeof(frame), result), "NON_FINITE"));
  frame[7] = 0x41; frame[8] = 0xC8; // 25 mg/L, outside sensor range.
  updateCRC(frame, sizeof(frame));
  assert(!strcmp(decode(frame, sizeof(frame), result), "OUT_OF_RANGE"));
  uint8_t exception[] = {1,0x83,2,0,0};
  updateCRC(exception, sizeof(exception));
  assert(!strcmp(decode(exception, sizeof(exception), result), "MODBUS_EXCEPTION"));
  puts("SEN0681 protocol checks passed");
}
