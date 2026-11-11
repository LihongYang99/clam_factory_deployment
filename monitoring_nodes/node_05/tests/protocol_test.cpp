#include "../firmware/node_05_ec/Protocol.h"
#include <cassert>
#include <iostream>

ezoec::Reply receive(const char* bytes) {
  ezoec::Reply reply;
  while (*bytes) reply.push(uint8_t(*bytes++));
  return reply;
}

int main() {
  double value = 0;
  auto reply = receive("\r\n1413.25\r\n*OK\r");
  assert(!reply.result(true));
  assert(ezoec::conductivity(reply.data, value) && value == 1413.25);
  assert(reply.count == strlen("\r\n1413.25\r\n*OK\r"));
  assert(ezoec::conductivity("0", value) && value == 0);
  for (const char* bad : {"", "-1", "nan", "inf", "12x", "12,0.5", " ", ".", "1.2.3"})
    assert(!ezoec::conductivity(bad, value));
  assert(!receive("*OK\r").result(false));
  assert(receive("*OK\r").result(true));
  assert(receive("1413\r").result(true));  // Missing acknowledgement is not success.
  assert(receive("1413\r*ER\r").result(true));
  assert(receive("*RS\r").result(false));
  assert(receive("1413\r1414\r*OK\r").result(true));
  assert(receive("1413\xff\r*OK\r").result(true));
  assert(ezoec::setting("?K,10.00", "?K,", value) && value == 10);
  assert(ezoec::setting("?t,25.00", "?T,", value) && value == 25);
  assert(ezoec::setting("?CAL,0", "?Cal,", value) && value == 0);
  assert(!ezoec::setting("?K,", "?K,", value));
  assert(!ezoec::startsWith("?I", "?I,EC,"));
  assert(ezoec::startsWith("?i,EC,2.17", "?I,EC,"));
  ezoec::Reply longLine;
  for (int i = 0; i < 65; ++i) longLine.push('1');
  assert(longLine.result(true));
  ezoec::Reply tooManyBytes;
  for (int i = 0; i < 129; ++i) tooManyBytes.push('\r');
  assert(tooManyBytes.truncated && tooManyBytes.count == 128);
  std::cout << "EZO-EC protocol checks passed\n";
}
