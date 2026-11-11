#pragma once
#include <stddef.h>
#include <string.h>

// Bounded line input; an overflowed line is always rejected, even after backspace.
struct CalibrationInput {
  char text[48]{};
  size_t length = 0;
  bool overflow = false;
  bool push(char c) {
    if (c == '\r') return false;
    if (c == '\n') {
      while (length && (text[length-1] == ' ' || text[length-1] == '\t')) --length;
      size_t start = 0;
      while (start < length && (text[start] == ' ' || text[start] == '\t')) ++start;
      length -= start;
      memmove(text, text + start, length);
      text[length] = 0;
      return true;
    }
    if (c == '\b' || c == 127) { if (length) --length; return false; }
    if (length < sizeof(text)-1) text[length++] = c;
    else overflow = true;
    return false;
  }
  void clear() { length = 0; overflow = false; text[0] = 0; }
};
