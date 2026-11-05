#include "../firmware/node_01_do/SerialLog.h"
#include <cassert>
#include <string>
#include <cstdio>

struct Port {
  int capacity = 64;
  bool shortWrite = false;
  bool newlineFailure = false;
  std::string output;
  explicit operator bool() const { return false; }
  int availableForWrite() const { return capacity; }
  size_t write(const uint8_t* data, size_t size) {
    if (shortWrite) --size;
    output.append(reinterpret_cast<const char*>(data), size);
    return size;
  }
  size_t write(char c) {
    if (newlineFailure) return 0;
    output += c;
    return 1;
  }
};

int main() {
  Port port;
  // USB may initially report disconnected; a writable buffer must still accept logs.
  assert(!bool(port));
  assert(writeLogLine(port, "BOOT"));
  assert(port.output == "BOOT\n");
  port.output.clear();
  port.capacity = 4;
  assert(!writeLogLine(port, "BOOT"));
  assert(port.output.empty());
  port.capacity = 5;
  assert(writeLogLine(port, "BOOT"));
  port.shortWrite = true;
  assert(!writeLogLine(port, "BOOT"));
  port.shortWrite = false;
  port.newlineFailure = true;
  assert(!writeLogLine(port, "BOOT"));
  puts("Serial logging checks passed");
}
