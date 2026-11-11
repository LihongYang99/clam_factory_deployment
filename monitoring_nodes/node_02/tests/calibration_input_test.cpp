#include <cassert>
#include "../firmware/node_02_orp/CalibrationInput.h"
void send(CalibrationInput& p, const char* s) { while (*s) p.push(*s++); }
int main() {
 CalibrationInput p;
 send(p,"  CAL POINT2 600 CONFIRM \t\r\n");
 assert(!strcmp(p.text,"CAL POINT2 600 CONFIRM") && !p.overflow);
 p.clear(); send(p,"CAL STATUX\bS\n"); assert(!strcmp(p.text,"CAL STATUS"));
 p.clear(); send(p,"CAL STATUX\x7f" "S\n"); assert(!strcmp(p.text,"CAL STATUS"));
 p.clear(); send(p,"  \r\n"); assert(p.length==0);
 p.clear(); for(int i=0;i<80;++i) p.push('A'); send(p,"\b\n"); assert(p.overflow);
 p.clear(); send(p,"CAL STATUS\n"); assert(!p.overflow && !strcmp(p.text,"CAL STATUS"));
}
