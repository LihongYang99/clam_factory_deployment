#include <cassert>
#include "../firmware/node_02_orp/Protocol.h"
int main() {
 uint8_t ack[] = {1,16,1,32,0,2,0x41,0xfe};
 assert(!sen0709::calibrationAck(ack,8));
 assert(!strcmp(sen0709::calibrationAck(ack,0),"TIMEOUT"));
 assert(!strcmp(sen0709::calibrationAck(ack,3),"SHORT_FRAME"));
 ack[7]^=1; assert(!strcmp(sen0709::calibrationAck(ack,8),"CRC_ERROR"));
 uint8_t ex[] = {1,0x90,2,0,0};
 auto crc=sen0709::crc16(ex,3); ex[3]=crc; ex[4]=crc>>8;
 assert(!strcmp(sen0709::calibrationAck(ex,5),"MODBUS_EXCEPTION"));
 assert(!strcmp(sen0709::calibrationAck(sen0709::request,8),"UNEXPECTED_FRAME"));
 // Captured on Node 02: valid CRC does not make this undocumented reply an ACK.
 const uint8_t captured[] = {0x01,0x90,0x01,0x20,0x00,0x01,0x00,0x21};
 assert(sen0709::crc16(captured,6)==0x2100);
 assert(!strcmp(sen0709::calibrationAck(captured,8),"UNEXPECTED_FRAME"));
}
