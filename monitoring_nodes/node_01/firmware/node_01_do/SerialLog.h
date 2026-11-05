#pragma once
#include <cstddef>
#include <cstdint>
#include <cstring>

template <typename Port>
bool writeLogLine(Port& port, const char* line) {
  const size_t length = strlen(line);
  // Admit the whole line before writing so diagnostics do not wait for TX space.
  if (port.availableForWrite() < int(length + 1)) return false;
  if (port.write(reinterpret_cast<const uint8_t*>(line), length) != length) return false;
  return port.write('\n') == 1;
}
