#!/usr/bin/env python3
"""Wortfall - terminal typing game to learn German (German = English = Urdu)."""
import curses
import json
import re
import locale
import math
import os
import random
import sys
import time

from words import WORDS
import audio

USE_URDU_SCRIPT = "--urdu-script" in sys.argv
BULLET_SPEED = 90.0   # visual units per second (a row counts as 2 units)
CANNON_SPEED = 60.0   # columns per second
MAP = {"ä": "a", "ö": "o", "ü": "u", "ß": "ss"}

FRAMES = (
    (" * ", "*#*", " * "),
    ("\\ | /", "- * -", "/ | \\"),
    (".  *  .", " *   * ", ".  *  ."),
    ("'     '", "       ", ".     ."),
)


def norm(s):
    s = s.lower()
    return "".join(MAP.get(c, c) for c in s)


ROMAN = {w[1].lower(): w[4] for w in WORDS}
PREFERRED = ["nouns", "family", "people", "places", "numbers", "weekdays", "months", "time",
             "colors", "food", "animals", "body", "home", "verbs", "adjectives", "greetings",
             "questions", "pronouns", "prepositions", "connectors"]
NICE = {"all": "All words", "nouns": "Nouns", "family": "Family & relationships",
        "weekdays": "Days of the week", "months": "Months", "colors": "Colors"}


def keyof(s):
    """Typed form of a word: umlauts folded, spaces and punctuation ignored."""
    return re.sub(r"[^a-z0-9]", "", norm(s))


def cat_label(name):
    return NICE.get(name, name.capitalize())


def load_pool():
    """{category: [(article, german, english, urdu_script, urdu_roman), ...]} from words.json."""
    cats = {}
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "words.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = []
    for e in data:
        if not isinstance(e, dict):
            continue
        de, en = str(e.get("de", "")).strip(), str(e.get("en", "")).strip()
        if not de or not en:
            continue
        art, parts = "", de.split(" ", 1)
        if len(parts) == 2 and parts[0] in ("der", "die", "das"):
            art, de = parts
        if not keyof(de):
            continue
        ur = e.get("ur") or ""
        item = (art, de, en, ur, ROMAN.get(de.lower(), ur))
        cats.setdefault(e.get("category") or "other", []).append(item)
        if e.get("pos") == "noun":
            cats.setdefault("nouns", []).append(item)
    if not cats:
        cats = {"all": list(WORDS)}
    allw, seen = [], set()
    for items in cats.values():
        for it in items:
            if (it[0], it[1]) not in seen:
                seen.add((it[0], it[1]))
                allw.append(it)
    ordered = {"all": allw}
    for c in [c for c in PREFERRED if c in cats] + sorted(c for c in cats if c not in PREFERRED):
        ordered[c] = cats[c]
    return ordered


class Word:
    def __init__(self, entry, x, y):
        self.art, self.de, self.en, self.ur_script, self.ur_roman = entry
        self.key = keyof(self.de)
        self.typed = 0
        self.x = x
        self.y = y
        self.dying = False
        ur = self.ur_script if USE_URDU_SCRIPT else self.ur_roman
        self.prefix = (self.art + " ") if self.art else ""
        self.suffix = f" = {self.en}" + (f" = {ur}" if ur else "")
        self.width = len(self.prefix) + len(self.de) + len(self.suffix)

    @property
    def cx(self):
        return self.x + len(self.prefix) + len(self.de) // 2

    def typed_chars(self):
        used, n = 0, 0
        for ch in self.de:
            step = len(keyof(ch))
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


def new_game(pool):
    return {
        "words": [], "bullets": [], "particles": [], "blasts": [],
        "pool": pool,
        "target": None, "score": 0, "killed": 0, "missed": 0,
        "combo": 0, "best_combo": 0, "last_spawn": 0.0, "speed": 1.0,
        "cannon_x": None, "aim_dx": 0.0, "flash": 0.0,
    }


def level(g):
    return g["killed"] // 8 + 1


def spawn(g, w):
    live = [o.key for o in g["words"] if not o.dying]
    pool = [e for e in g["pool"] if not any(
        k.startswith(keyof(e[1])) or keyof(e[1]).startswith(k) for k in live)]
    entry = random.choice(pool or g["pool"])
    probe = Word(entry, 0, 0)
    if probe.width >= w - 2:
        return
    for _ in range(10):
        x = random.randint(0, w - probe.width - 1)
        if all(abs(o.x - x) > 6 or o.y > 3 for o in g["words"]):
            break
    probe.x, probe.y = x, 0.0
    g["words"].append(probe)


def add_blast(g, wd, hit):
    """Word destruction: flash, disintegrating text, center burst, flying sparks."""
    text = wd.prefix + wd.de + wd.suffix
    g["blasts"].append({"x": wd.x, "y": wd.y, "cx": wd.cx, "text": text, "hit": hit,
                        "t": 0.0, "gone": [random.random() for _ in text]})
    chars = "*+.'`%#" if hit else ".,'"
    colors = (5, 2, 6, 3) if hit else (2,)
    for i in range(0, len(text), 2 if hit else 4):
        g["particles"].append({
            "x": float(wd.x + i), "y": float(wd.y),
            "vx": random.uniform(-16, 16) if hit else random.uniform(-4, 4),
            "vy": random.uniform(-9, 1) if hit else random.uniform(-3, 0),
            "life": random.uniform(0.35, 0.7),
            "ch": random.choice(chars), "color": random.choice(colors)})


def handle_key(g, ch):
    if not isinstance(ch, str) or len(ch) != 1 or not ch.isprintable() or ch == " ":
        return
    c = keyof(ch)
    if not c:
        return
    tgt = g["target"]
    if tgt is None:
        cands = [w for w in g["words"] if not w.dying and w.key.startswith(c)]
        if not cands:
            g["combo"] = 0
            return
        tgt = max(cands, key=lambda w: w.y)
        g["target"] = tgt
    if tgt.key[tgt.typed:].startswith(c):
        tgt.typed += len(c)
        g["combo"] += 1
        g["best_combo"] = max(g["best_combo"], g["combo"])
        if tgt.typed >= len(tgt.key):
            tgt.dying = True
            g["bullets"].append({"x": None, "y": None, "dx": 0.0, "dy": -1.0,
                                 "word": tgt, "trail": []})
            g["target"] = None
    else:
        g["combo"] = 0


def update(g, dt, now, h, w):
    if g["cannon_x"] is None:
        g["cannon_x"] = w / 2
    interval = max(0.9, 2.6 - level(g) * 0.15)
    if now - g["last_spawn"] > interval:
        spawn(g, w)
        g["last_spawn"] = now
    speed = (1.2 + level(g) * 0.25) * g["speed"]
    for wd in list(g["words"]):
        if wd.dying:
            continue
        wd.y += speed * dt
        if wd.y >= h - 4:
            g["words"].remove(wd)
            g["missed"] += 1
            g["combo"] = 0
            if g["target"] is wd:
                g["target"] = None
            add_blast(g, wd, hit=False)

    # cannon slides toward the word being typed (or the word just shot)
    aim = None
    if g["target"] is not None:
        aim = g["target"].cx
    elif g["bullets"]:
        aim = g["bullets"][0]["word"].cx
    ax = g["cannon_x"]
    if aim is not None:
        step = CANNON_SPEED * dt
        ax += max(-step, min(step, aim - ax))
    ax = max(3, min(w - 4, ax))
    g["cannon_x"] = ax
    g["aim_dx"] = (aim - ax) if aim is not None else 0.0

    # homing bullets
    for b in list(g["bullets"]):
        wd = b["word"]
        if b["x"] is None:
            b["x"], b["y"] = g["cannon_x"], h - 5.0
            g["flash"] = 0.12
        dx, dy = wd.cx - b["x"], wd.y - b["y"]
        dist = math.hypot(dx, dy * 2)
        step = BULLET_SPEED * dt
        b["dx"], b["dy"] = dx, dy
        if dist <= max(step, 1.5):
            if wd in g["words"]:
                g["words"].remove(wd)
            g["bullets"].remove(b)
            g["killed"] += 1
            g["score"] += len(wd.de) * 10 + g["combo"]
            add_blast(g, wd, hit=True)
            audio.get_speaker().speak((wd.art + " " + wd.de).strip())
        else:
            b["trail"].append((b["x"], b["y"]))
            b["trail"] = b["trail"][-4:]
            f = step / dist
            b["x"] += dx * f
            b["y"] += dy * f

    for p in list(g["particles"]):
        p["life"] -= dt
        if p["life"] <= 0 or p["y"] >= h:
            g["particles"].remove(p)
            continue
        p["vy"] += 14 * dt
        p["x"] += p["vx"] * dt
        p["y"] += p["vy"] * dt
    for bl in list(g["blasts"]):
        bl["t"] += dt
        if bl["t"] > 0.45:
            g["blasts"].remove(bl)
    g["flash"] = max(0.0, g["flash"] - dt)


def draw_blasts(win, g):
    for bl in g["blasts"]:
        t, y = bl["t"], int(bl["y"])
        col = curses.color_pair(5 if bl["hit"] else 2) | curses.A_BOLD
        if t < 0.1:
            safe_add(win, y, bl["x"], bl["text"], col | curses.A_REVERSE)
        elif t < 0.4:
            p = (t - 0.1) / 0.3
            txt = "".join(c if r > p else " " for c, r in zip(bl["text"], bl["gone"]))
            safe_add(win, y, bl["x"], txt, col)
        if bl["hit"] and t < 0.4:
            fcol = curses.color_pair(5 if t < 0.2 else 2) | curses.A_BOLD
            for i, row in enumerate(FRAMES[min(3, int(t / 0.1))]):
                safe_add(win, y - 1 + i, int(bl["cx"]) - len(row) // 2, row, fcol)


def draw_cannon(win, g, h, w):
    cx = int(round(g["cannon_x"])) if g["cannon_x"] is not None else w // 2
    dx = g["aim_dx"]
    barrel = "/" if dx > 6 else "\\" if dx < -6 else "|"
    red = curses.color_pair(2) | curses.A_BOLD
    if g["flash"] > 0:
        safe_add(win, h - 5, cx - 1, "\\*/", curses.color_pair(5) | curses.A_BOLD)
    safe_add(win, h - 4, cx, barrel, curses.color_pair(5) | curses.A_BOLD)
    safe_add(win, h - 3, cx - 1, "▄█▄", red)
    safe_add(win, h - 2, cx - 2, "▟███▙", red)
    safe_add(win, h - 1, cx - 3, "(o)=(o)", curses.color_pair(3) | curses.A_BOLD)


def draw(win, g, h, w):
    win.erase()
    hud = (f" Score {g['score']}   Level {level(g)}   Correct {g['killed']}   "
           f"Missed {g['missed']}   Combo {g['combo']}   Speed {g['speed']:.2f}x   Sound {'ON' if audio.get_speaker().enabled else 'OFF'} ")
    safe_add(win, 0, 0, hud, curses.color_pair(5) | curses.A_BOLD)
    hint = "ESC menu  TAB reset  F2 sound"
    if w >= len(hud) + len(hint) + 2:
        safe_add(win, 0, w - len(hint) - 1, hint, curses.color_pair(4))
    for wd in g["words"]:
        if not wd.dying:
            draw_word(win, wd, wd is g["target"])
    draw_blasts(win, g)
    for p in g["particles"]:
        safe_add(win, int(p["y"]), int(p["x"]), p["ch"],
                 curses.color_pair(p["color"]) | curses.A_BOLD)
    for b in g["bullets"]:
        if b["x"] is None:
            continue
        for tx, ty in b["trail"]:
            safe_add(win, int(ty), int(tx), ".", curses.color_pair(4))
        if abs(b["dx"]) < abs(b["dy"]) * 0.5:
            glyph = "|"
        else:
            glyph = "/" if b["dx"] > 0 else "\\"
        safe_add(win, int(b["y"]), int(b["x"]), glyph, curses.color_pair(5) | curses.A_BOLD)
    draw_cannon(win, g, h, w)
    win.refresh()


BGS_256 = (-1, 17, 52, 22, 53, 58, 23, 54)
BGS_8 = (-1, curses.COLOR_BLUE, curses.COLOR_BLACK)
FG_256 = (46, 203, 255, 51, 226, 207)
FG_8 = (curses.COLOR_GREEN, curses.COLOR_RED, curses.COLOR_WHITE,
        curses.COLOR_CYAN, curses.COLOR_YELLOW, curses.COLOR_MAGENTA)
BG_EVERY = 20  # correct words per background change


def apply_theme(win, idx):
    big = curses.COLORS >= 256
    bgs, fgs = (BGS_256, FG_256) if big else (BGS_8, FG_8)
    bg = bgs[idx % len(bgs)]
    for n, fg in enumerate(fgs, 1):
        curses.init_pair(n, fg, bg)
    curses.init_pair(7, fgs[2], bg)
    win.bkgd(" ", curses.color_pair(7))


def center(win, y, s, attr=0):
    _, w = win.getmaxyx()
    safe_add(win, y, max(0, (w - len(s)) // 2), s, attr)


def draw_menu(win, h, w, urdu, speed, last, cat):
    win.erase()
    y = max(1, h // 2 - 7)
    gold = curses.color_pair(5) | curses.A_BOLD
    center(win, y, "W O R T F A L L", gold)
    center(win, y + 1, "German = English = Urdu", curses.color_pair(4))
    center(win, y + 3, f"C / \u2190\u2192  Category: {cat}", curses.color_pair(5) | curses.A_BOLD)
    center(win, y + 4, "ENTER   Start game", curses.color_pair(1) | curses.A_BOLD)
    center(win, y + 5, f"U       Urdu: {'script' if urdu else 'roman'}", curses.color_pair(3))
    center(win, y + 6, f"+ / -   Start speed: {speed:.2f}x", curses.color_pair(3))
    sp = audio.get_speaker()
    center(win, y + 7, f"M / F2  Sound: {'ON' if sp.enabled else 'OFF'}" + ("" if sp.available else " (no audio tool)"), curses.color_pair(3))
    center(win, y + 8, "Q / ESC Quit", curses.color_pair(3))
    if last:
        center(win, y + 10, last, curses.color_pair(6))
    win.refresh()


def main(stdscr):
    global USE_URDU_SCRIPT
    curses.curs_set(0)
    curses.start_color()
    curses.use_default_colors()
    stdscr.nodelay(True)
    stdscr.keypad(True)
    apply_theme(stdscr, 0)

    theme, start_speed, last_result = 0, 1.0, ""
    cats = load_pool()
    names = list(cats)
    cat_i = 0
    g = None  # None = menu
    last = time.time()
    while True:
        h, w = stdscr.getmaxyx()
        now = time.time()
        dt = min(now - last, 0.1)
        last = now
        try:
            while True:
                ch = stdscr.get_wch()
                if g is None:
                    if ch in ("\n", "\r", curses.KEY_ENTER):
                        g = new_game(cats[names[cat_i]])
                        g["speed"] = start_speed
                        theme = 0
                        apply_theme(stdscr, 0)
                    elif ch == "\x1b" or (isinstance(ch, str) and ch.lower() == "q"):
                        return
                    elif ch == curses.KEY_F0 + 2 or (isinstance(ch, str) and ch.lower() == "m"):
                        audio.get_speaker().toggle()
                    elif ch in (curses.KEY_RIGHT, curses.KEY_DOWN) or (isinstance(ch, str) and ch.lower() == "c"):
                        cat_i = (cat_i + 1) % len(names)
                    elif ch in (curses.KEY_LEFT, curses.KEY_UP):
                        cat_i = (cat_i - 1) % len(names)
                    elif isinstance(ch, str) and ch.lower() == "u":
                        USE_URDU_SCRIPT = not USE_URDU_SCRIPT
                    elif ch in ("+", "="):
                        start_speed = min(3.0, round(start_speed + 0.25, 2))
                    elif ch in ("-", "_"):
                        start_speed = max(0.25, round(start_speed - 0.25, 2))
                    continue
                if ch == "\x1b":
                    last_result = (f"Last game: score {g['score']}  correct {g['killed']}"
                                   f"  missed {g['missed']}  best combo {g['best_combo']}")
                    start_speed = g["speed"]
                    g = None
                    theme = 0
                    apply_theme(stdscr, 0)
                elif ch in ("+", "="):
                    g["speed"] = min(3.0, round(g["speed"] + 0.25, 2))
                elif ch in ("-", "_"):
                    g["speed"] = max(0.25, round(g["speed"] - 0.25, 2))
                elif ch in ("/", curses.KEY_F0 + 2):
                    audio.get_speaker().toggle()
                elif ch == "\t":
                    if g["target"]:
                        g["target"].typed = 0
                        g["target"] = None
                else:
                    handle_key(g, ch)
        except curses.error:
            pass
        if g is None:
            draw_menu(stdscr, h, w, USE_URDU_SCRIPT, start_speed, last_result,
                      f"{cat_label(names[cat_i])} ({len(cats[names[cat_i]])})")
        else:
            if h > 8 and w > 30:
                update(g, dt, now, h, w)
            idx = g["killed"] // BG_EVERY
            if idx != theme:
                theme = idx
                apply_theme(stdscr, theme)
            draw(stdscr, g, h, w)
        time.sleep(0.016)


if __name__ == "__main__":
    locale.setlocale(locale.LC_ALL, "")
    os.environ.setdefault("ESCDELAY", "25")
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass
