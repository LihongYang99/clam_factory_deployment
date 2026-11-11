#include "../firmware/node_05_ec/Calibration.h"
#include <cassert>
#include <iostream>

int main() {
  using Cal = ezoec::Calibration;
  Cal cal;
  assert(cal.check(Cal::DRY));
  cal.begin();
  assert(!cal.check(Cal::DRY) && cal.check(Cal::LOW_POINT));
  cal.written(true);
  cal.begin();  // Repeated BEGIN must not lose the acknowledged dry step.
  assert(!cal.check(Cal::LOW_POINT) && cal.check(Cal::DRY) && cal.check(Cal::HIGH_POINT));
  cal.written(false);
  cal.begin();
  assert(cal.check(Cal::LOW_POINT) && cal.check(Cal::HIGH_POINT));
  assert(cal.next == Cal::UNCERTAIN);
  cal.end();
  cal.begin();
  for (auto step : {Cal::DRY, Cal::LOW_POINT, Cal::HIGH_POINT}) {
    assert(!cal.check(step));
    cal.written(true);
  }
  assert(cal.next == Cal::VERIFY && cal.check(Cal::HIGH_POINT));
  assert(cal.sequenceConfirmed(2));
  assert(!cal.sequenceConfirmed(0) && !cal.sequenceConfirmed(1));
  cal.end();
  assert(!cal.sequenceConfirmed(2));

  ezoec::CalibrationInput input;
  for (char c : "  CAL LOW 12880 CONFIRM \r\n") {
    if (!c) break;
    if (input.push(c)) assert(!strcmp(input.text, "CAL LOW 12880 CONFIRM"));
  }
  assert(!input.invalid);
  input = {};
  for (int i = 0; i < 60; ++i) input.push('X');
  for (int i = 0; i < 60; ++i) input.push('\b');
  input.push('\n');
  assert(input.invalid);  // Backspacing cannot rescue an overflowed command.
  input = {};
  input.push('\0');
  assert(input.invalid);
  std::cout << "EZO-EC calibration input and sequencing checks passed\n";
}
