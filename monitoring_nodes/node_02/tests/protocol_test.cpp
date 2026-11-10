#include "../firmware/node_02_orp/Protocol.h"
#include <cassert>
int main() {
  using namespace sen0709;
  Reading r{};
  uint8_t frame[]={1,3,4,1,0x35,1,1,0x2b,0x91};
  assert(!decode(frame,9,r) && r.orp_mv==309 && std::abs(r.temperature_c-25.7f)<0.01);
  frame[3]=0xff; frame[4]=0x9c; frame[5]=0xff; frame[6]=0xce;
  auto crc=crc16(frame,7); frame[7]=crc;frame[8]=crc>>8;
  assert(!decode(frame,9,r) && r.orp_mv==-100 && r.temperature_c==-5);
  frame[8]^=1;
  assert(decode(frame,9,r) && r.orp_mv==-100);
  assert(decode(frame,0,r));
}
