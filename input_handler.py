"""Keyboard input: typing, backspace, submit, pause, quit, UTF-8 umlauts."""

import curses

BACKSPACE_KEYS = (curses.KEY_BACKSPACE, 127, 8, curses.KEY_DC)
ENTER_KEYS = (curses.KEY_ENTER, 10, 13)
ESC_KEY = 27

_MULTIBYTE_MAP = {0xA4: "ae", 0xB6: "oe", 0xBC: "ue", 0x9F: "ss"}


class InputHandler:
    def __init__(self, state):
        self.state = state
        self._pending_c3 = False

    def handle(self, key):
        state = self.state

        if self._pending_c3:
            self._pending_c3 = False
            if isinstance(key, int) and (key & 0xFF) in _MULTIBYTE_MAP:
                self._append(_MULTIBYTE_MAP[key & 0xFF])
            return

        if state.paused:
            if key in (ESC_KEY, ord("p"), ord("P")):
                state.paused = False
                state.flash("", 0)
            elif key in (ord("q"), ord("Q")):
                state.quit_to_menu = True
            return

        if key == ESC_KEY:
            state.paused = True
            state.flash("", 0)
        elif key in BACKSPACE_KEYS:
            state.input_buffer = state.input_buffer[:-1]
        elif key in ENTER_KEYS:
            state.submit_input()
        elif key == curses.KEY_RESIZE:
            pass
        elif key == 195:
            self._pending_c3 = True
        elif 32 <= key <= 126:
            self._append(chr(key))

    def _append(self, ch):
        if len(self.state.input_buffer) < 40:
            self.state.input_buffer += ch
