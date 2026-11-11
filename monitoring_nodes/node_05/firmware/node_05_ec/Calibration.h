#pragma once
#include <cstring>
#include <cstddef>

namespace ezoec {

// Same bounded USB line handling as Node 02; reject control bytes and overflow.
struct CalibrationInput {
  char text[48]{};
  size_t length = 0;
  bool invalid = false;
  bool push(char c) {
    if (c == '\r') return false;
    if (c == '\n') {
      while (length && (text[length - 1] == ' ' || text[length - 1] == '\t')) --length;
      size_t start = 0;
      while (start < length && (text[start] == ' ' || text[start] == '\t')) ++start;
      length -= start;
      memmove(text, text + start, length);
      text[length] = 0;
      return true;
    }
    if (c == '\b' || c == 127) { if (length) --length; return false; }
    if ((c < 32 && c != '\t') || c > 126 || length == sizeof(text) - 1)
      invalid = true;
    else text[length++] = c;
    return false;
  }
};

struct Calibration {
  enum Step { DRY, LOW_POINT, HIGH_POINT, VERIFY, UNCERTAIN };
  bool active = false;
  Step next = DRY;

  void begin() { if (!active) { active = true; next = DRY; } }
  void end() { active = false; next = DRY; }
  const char* stage() const {
    const char* names[] = {"DRY", "LOW", "HIGH", "VERIFY", "UNCERTAIN"};
    return names[next];
  }
  const char* check(Step step) const {
    if (!active) return "MODE_OFF";
    if (next == UNCERTAIN) return "PREVIOUS_WRITE_UNCONFIRMED";
    if (next != step) return "WRONG_STEP";
    return nullptr;
  }
  void written(bool acknowledged) {
    next = acknowledged ? Step(int(next) + 1) : UNCERTAIN;
  }
  bool sequenceConfirmed(double storedMode) const {
    return active && next == VERIFY && storedMode == 2;
  }
};

}  // namespace ezoec
