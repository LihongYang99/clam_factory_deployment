#include <cassert>
#include "../firmware/node_02_orp/Protocol.h"
int main() {
  uint8_t frame[13];
  const uint8_t first[] = {1,16,1,32,0,2,4,0,1,0,86,0x2d,0xd9};
  const uint8_t second[] = {1,16,1,32,0,2,4,0,2,1,0,0x5c,0x77};
  sen0709::calibrationFrame(1,86,frame);
  assert(!memcmp(frame,first,13));
  sen0709::calibrationFrame(2,256,frame);
  assert(!memcmp(frame,second,13));
  const uint8_t first200[] = {1,16,1,32,0,2,4,0,1,0,200,0xac,0x71};
  const uint8_t second600[] = {1,16,1,32,0,2,4,0,2,2,88,0x5d,0x7d};
  sen0709::calibrationFrame(1,200,frame);
  assert(!memcmp(frame,first200,13));
  sen0709::calibrationFrame(2,600,frame);
  assert(!memcmp(frame,second600,13));
}
