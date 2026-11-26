#!/usr/bin/env python3
"""Wortfall - terminal typing game to learn German (German = English = Urdu)."""
import curses
import random
import sys
import time

from words import WORDS

USE_URDU_SCRIPT = "--urdu-script" in sys.argv
LIVES = 5
BULLET_SPEED = 45.0  # rows per second

MAP = {"ä": "a", "ö": "o", "ü": "u", "ß": "ss"}


def norm(s):
    s = s.lower()
    return "".join(MAP.get(c, c) for c in s)


class Word:
    def __init__(self, entry, x, y):
        self.art, self.de, self.en, self.ur_script, self.ur_roman = entry
        self.key = norm(self.de)
        self.typed = 0
        self.x = x
        self.y = y
        self.dying = False
        ur = self.ur_script if USE_URDU_SCRIPT else self.ur_roman
        self.prefix = (self.art + " ") if self.art else ""
        self.suffix = f" = {self.en} = {ur}"
        self.width = len(self.prefix) + len(self.de) + len(self.suffix)

    @property
    def cx(self):
        return self.x + len(self.prefix) + len(self.de) // 2

    def typed_chars(self):
        """How many characters of self.de are covered by self.typed key chars."""
        used, n = 0, 0
        for ch in self.de:
            step = len(norm(ch))
            if used + step > self.typed:
                break
            used += step
            n += 1
        return n


def safe_add(win, y, x, s, attr=0):
    h, w = win.getmaxyx()
    if y < 0 or y >= h or x >= w:
        return
    if x < 0:
        s, x = s[-x:], 0
    s = s[: max(0, w - x - (1 if y == h - 1 else 0))]
    try:
        win.addstr(y, x, s, attr)
    except curses.error:
        pass


def draw_word(win, wd, is_target):
    pair_done = curses.color_pair(1) | curses.A_BOLD
    pair_todo = curses.color_pair(3) | (curses.A_BOLD if is_target else 0)
    pair_meta = curses.color_pair(4)
    x = wd.x
    safe_add(win, int(wd.y), x, wd.prefix, pair_meta)
    x += len(wd.prefix)
    done = wd.typed_chars()
    safe_add(win, int(wd.y), x, wd.de[:done], pair_done)
    safe_add(win, int(wd.y), x + done, wd.de[done:], pair_todo)
    x += len(wd.de)
    safe_add(win, int(wd.y), x, wd.suffix, pair_meta)


def new_game():
    return {
        "words": [], "bullets": [], "target": None, "score": 0,
        "killed": 0, "lives": LIVES, "combo": 0, "best_combo": 0,
        "last_spawn": 0.0, "cannon_x": None, "over": False,
    }


def level(g):
    return g["killed"] // 8 + 1


def spawn(g, w):
    entry = random.choice(WORDS)
    probe = Word(entry, 0, 0)
    if probe.width >= w - 2:
        return
    for _ in range(10):
        x = random.randint(0, w - probe.width - 1)
        # avoid stacking on top of a word that's still near the top
        if all(abs(o.x - x) > 6 or o.y > 3 for o in g["words"]):
            break
    probe.x, probe.y = x, 0.0
    g["words"].append(probe)


def handle_key(g, ch):
    if not isinstance(ch, str) or len(ch) != 1 or not ch.isprintable() or ch == " ":
        return
    c = norm(ch)
    tgt = g["target"]
    if tgt is None:
        cands = [w for w in g["words"] if not w.dying and w.key.startswith(c)]
        if not cands:
            g["combo"] = 0
            return
        tgt = max(cands, key=lambda w: w.y)  # closest to the bottom
        g["target"] = tgt
    if tgt.key[tgt.typed:].startswith(c):
        tgt.typed += len(c)
        g["combo"] += 1
        g["best_combo"] = max(g["best_combo"], g["combo"])
        if tgt.typed >= len(tgt.key):
            tgt.dying = True
            g["cannon_x"] = tgt.cx
            g["bullets"].append({"x": tgt.cx, "y": None, "word": tgt})
            g["target"] = None
    else:
        g["combo"] = 0


def update(g, dt, now, h, w):
    interval = max(0.9, 2.6 - level(g) * 0.15)
    if now - g["last_spawn"] > interval:
        spawn(g, w)
        g["last_spawn"] = now
    speed = 1.2 + level(g) * 0.25
    for wd in list(g["words"]):
        if wd.dying:
            continue
        wd.y += speed * dt
        if wd.y >= h - 3:
            g["words"].remove(wd)
            g["lives"] -= 1
            g["combo"] = 0
            if g["target"] is wd:
                g["target"] = None
            if g["lives"] <= 0:
                g["over"] = True
    for b in list(g["bullets"]):
        if b["y"] is None:
            b["y"] = float(h - 3)
        b["y"] -= BULLET_SPEED * dt
        if b["y"] <= b["word"].y:
            if b["word"] in g["words"]:
                g["words"].remove(b["word"])
            g["bullets"].remove(b)
            g["killed"] += 1
            g["score"] += len(b["word"].de) * 10 + g["combo"]


def draw(win, g, h, w):
    win.erase()
    hud = f" Score {g['score']}   Level {level(g)}   Lives {'♥' * g['lives']}{'·' * (LIVES - g['lives'])}   Combo {g['combo']} "
    safe_add(win, 0, 0, hud, curses.color_pair(5) | curses.A_BOLD)
    for wd in g["words"]:
        draw_word(win, wd, wd is g["target"])
    for b in g["bullets"]:
        safe_add(win, int(b["y"]), int(b["x"]), "|", curses.color_pair(2) | curses.A_BOLD)
    cx = int(g["cannon_x"] if g["cannon_x"] is not None else w // 2)
    safe_add(win, h - 2, cx - 1, "/A\\", curses.color_pair(2) | curses.A_BOLD)
    safe_add(win, h - 1, cx - 2, "[___]", curses.color_pair(2))
    safe_add(win, h - 2, 0, "ESC quit  TAB reset word", curses.color_pair(4))
    if g["over"]:
        msg = [
            "GAME OVER",
            f"Score {g['score']}  Words {g['killed']}  Best combo {g['best_combo']}",
            "R = restart   Q = quit",
        ]
        for i, line in enumerate(msg):
            safe_add(win, h // 2 - 1 + i, max(0, (w - len(line)) // 2), line,
                     curses.color_pair(6) | curses.A_BOLD)
    win.refresh()


def main(stdscr):
    curses.curs_set(0)
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_GREEN, -1)   # typed
    curses.init_pair(2, curses.COLOR_RED, -1)     # cannon / bullet
    curses.init_pair(3, curses.COLOR_WHITE, -1)   # untyped
    curses.init_pair(4, curses.COLOR_CYAN, -1)    # meanings
    curses.init_pair(5, curses.COLOR_YELLOW, -1)  # HUD
    curses.init_pair(6, curses.COLOR_MAGENTA, -1) # game over
    stdscr.nodelay(True)
    stdscr.keypad(True)

    g = new_game()
    last = time.time()
    while True:
        h, w = stdscr.getmaxyx()
        now = time.time()
        dt = min(now - last, 0.1)
        last = now
        try:
            while True:
                ch = stdscr.get_wch()
                if ch == "\x1b":
                    return
                if g["over"]:
                    if isinstance(ch, str) and ch.lower() == "r":
                        g = new_game()
                    elif isinstance(ch, str) and ch.lower() == "q":
                        return
                elif ch == "\t":
                    if g["target"]:
                        g["target"].typed = 0
                        g["target"] = None
                else:
                    handle_key(g, ch)
        except curses.error:
            pass
        if not g["over"] and h > 8 and w > 30:
            update(g, dt, now, h, w)
        draw(stdscr, g, h, w)
        time.sleep(0.016)


if __name__ == "__main__":
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass
