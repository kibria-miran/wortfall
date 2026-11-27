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
from sentences import SENTENCES
import mnemonics
import audio
import config

USE_URDU_SCRIPT = "--urdu-script" in sys.argv
BULLET_SPEED = 90.0   # visual units per second (a row counts as 2 units)
CANNON_SPEED = 60.0   # columns per second
FALL_SPEED = 1.45     # rows per second at 1.0x (does not grow with level)
MAX_WORDS = 7         # at most this many live words on screen at once
NUM_WIDTH = 3         # width of the " 1 " sequence-number field
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


# Memory hooks (Merkhilfe): German sentence -> its sound-alike breakdown + story.
MNEMONICS = {keyof(s[0]): s for s in mnemonics.SENTENCES}


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
    ordered = {"all": allw, "sentences": list(SENTENCES)}
    # the 20 Merkhilfe sentences join the sentence pool (skipping duplicates)
    seen_sent = {keyof(e[1]) for e in ordered["sentences"]}
    for s in mnemonics.SENTENCES:
        if keyof(s[0]) not in seen_sent:
            ordered["sentences"].append(("", s[0], s[1], "", s[2]))
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
        self.seq = 0
        ur = self.ur_script if USE_URDU_SCRIPT else self.ur_roman
        self.prefix = (self.art + " ") if self.art else ""
        self.suffix = f" = {self.en}" + (f" = {ur}" if ur else "")
        self.width = NUM_WIDTH + len(self.prefix) + len(self.de) + len(self.suffix)

    def num_text(self):
        """Fixed-width sequence number shown in front of the word."""
        return f"{self.seq:>2d} " if self.seq else " " * NUM_WIDTH

    @property
    def cx(self):
        return self.x + NUM_WIDTH + len(self.prefix) + len(self.de) // 2

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
    pair_num = curses.color_pair(5) | curses.A_BOLD
    x = wd.x
    safe_add(win, int(wd.y), x, wd.num_text(), pair_num)
    x += NUM_WIDTH
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
        "pool": pool, "category": None,
        "target": None, "score": 0, "killed": 0, "missed": 0,
        "combo": 0, "best_combo": 0, "last_spawn": 0.0, "speed": 1.0,
        "cannon_x": None, "aim_dx": 0.0, "flash": 0.0,
        "banner": None,   # (text, until) — sound-alike reminder after a sentence
        "help": False,    # Merkhilfe overlay open (game paused)
    }


def level(g):
    return g["killed"] // 8 + 1


# ---- saved game ----------------------------------------------------------
SAVE_VERSION = 1


def save_path():
    return config.APP_DIR / "savegame.json"


def read_save():
    """The saved game dict, or None when there is nothing usable to resume."""
    try:
        with open(save_path(), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("version") != SAVE_VERSION:
        return None
    try:
        float(data.get("saved_at", 0) or 0)
        int(data.get("score", 0))
        int(data.get("killed", 0))
        if not isinstance(data.get("words", []), list):
            return None
        if not isinstance(data.get("bullets", []), list):
            return None
    except (TypeError, ValueError):
        return None
    return data


def save_game(g):
    """Persist the current game so it can be resumed from the menu."""
    if g is None:
        return False
    words = list(g["words"])
    index = {id(w): i for i, w in enumerate(words)}
    data = {
        "version": SAVE_VERSION,
        "saved_at": time.time(),
        "category": g.get("category"),
        "urdu_script": USE_URDU_SCRIPT,
        "speed": g["speed"], "score": g["score"], "killed": g["killed"],
        "missed": g["missed"], "combo": g["combo"], "best_combo": g["best_combo"],
        "cannon_x": g["cannon_x"],
        "words": [{
            "entry": [w.art, w.de, w.en, w.ur_script, w.ur_roman],
            "x": w.x, "y": w.y, "typed": w.typed, "dying": w.dying, "seq": w.seq,
        } for w in words],
        "bullets": [{
            "word_index": index.get(id(b["word"]), -1),
            "x": b["x"], "y": b["y"], "dx": b["dx"], "dy": b["dy"],
            "trail": [list(t) for t in b["trail"]],
        } for b in g["bullets"]],
    }
    path = save_path()
    try:
        config.APP_DIR.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, path)
    except OSError:
        return False
    return True


def restore_game(data, cats):
    """Rebuild a game from read_save(); returns (game, category) or (None, None)."""
    global USE_URDU_SCRIPT
    try:
        cat = data.get("category")
        if cat not in cats:
            cat = "all" if "all" in cats else next(iter(cats))
        USE_URDU_SCRIPT = bool(data.get("urdu_script", USE_URDU_SCRIPT))
        g = new_game(cats[cat])
        g["category"] = cat
        g["speed"] = float(data.get("speed", 1.0))
        for key in ("score", "killed", "missed", "combo", "best_combo"):
            g[key] = int(data.get(key, 0))
        cx = data.get("cannon_x")
        g["cannon_x"] = float(cx) if cx is not None else None
        words = []
        for wd in data.get("words", []):
            entry = wd.get("entry") or []
            if len(entry) != 5:
                continue
            w = Word(tuple(str(p) for p in entry), int(wd.get("x", 0)),
                     float(wd.get("y", 1.0)))
            w.typed = int(wd.get("typed", 0))
            w.dying = bool(wd.get("dying", False))
            w.seq = int(wd.get("seq", 0))
            words.append(w)
        g["words"] = words
        for b in data.get("bullets", []):
            i = int(b.get("word_index", -1))
            if 0 <= i < len(words):
                g["bullets"].append({
                    "x": b.get("x"), "y": b.get("y"),
                    "dx": float(b.get("dx", 0.0)), "dy": float(b.get("dy", -1.0)),
                    "word": words[i],
                    "trail": [tuple(t) for t in b.get("trail", []) if len(t) == 2],
                })
        return g, cat
    except (AttributeError, KeyError, TypeError, ValueError):
        return None, None


def save_summary(data):
    """Short one-line description of a saved game for the menu."""
    killed = int(data.get("killed", 0))
    age = time.time() - float(data.get("saved_at", 0) or 0)
    return (f"score {data.get('score', 0)}  level {killed // 8 + 1}  "
            f"correct {killed}  saved {fmt_age(age)}")


def fmt_age(seconds):
    seconds = max(0, int(seconds))
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    return f"{seconds // 86400}d ago"


def spawn(g, w):
    sent = g.get("category") == "sentences"
    live_words = [o for o in g["words"] if not o.dying]
    if len(live_words) >= (3 if sent else MAX_WORDS):
        return
    if sent and any(o.y <= 3 for o in live_words):
        return   # sentences are wide: keep them vertically apart instead
    live = [o.key for o in g["words"] if not o.dying]
    pool = [e for e in g["pool"] if not any(
        k.startswith(keyof(e[1])) or keyof(e[1]).startswith(k) for k in live)]
    entry = random.choice(pool or g["pool"])
    probe = Word(entry, 0, 0)
    if probe.width >= w - 2:
        return
    for _ in range(10):
        x = random.randint(0, w - probe.width - 1)
        if sent or all(abs(o.x - x) > 6 or o.y > 3 for o in g["words"]):
            break
    probe.x, probe.y = x, 1.0
    g["words"].append(probe)


def number_words(g):
    """Number the live words 1..N so the lowest (most urgent) word is #1."""
    live = [w for w in g["words"] if not w.dying]
    live.sort(key=lambda w: (-w.y, w.x))
    for i, w in enumerate(live, 1):
        w.seq = i


def sequence_word(g):
    """The only word the player may type: the lowest live word (#1)."""
    live = [w for w in g["words"] if not w.dying]
    if not live:
        return None
    return min(live, key=lambda w: (-w.y, w.x))


def add_blast(g, wd, hit):
    """Word destruction: flash, disintegrating text, center burst, flying sparks."""
    text = wd.num_text() + wd.prefix + wd.de + wd.suffix
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
    if tgt is None or tgt.dying:
        tgt = sequence_word(g)
        if tgt is None:
            g["combo"] = 0
            return
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
            if g.get("category") == "sentences":
                mn = MNEMONICS.get(keyof(tgt.de))
                if mn:   # reinforce: remind the sound-alikes for a few seconds
                    g["banner"] = (
                        " \u00b7 ".join(f"{de} ~ {sounds[0]}" for de, en, ur, sounds in mn[3]),
                        time.time() + 6.0)
    else:
        g["combo"] = 0


def update(g, dt, now, h, w):
    if g["cannon_x"] is None:
        g["cannon_x"] = w / 2
    sent = g.get("category") == "sentences"
    interval = max(0.9, 2.6 - level(g) * 0.15) + (2.0 if sent else 0.0)
    if now - g["last_spawn"] > interval:
        spawn(g, w)
        g["last_spawn"] = now
    speed = FALL_SPEED * g["speed"] * (0.5 if sent else 1.0)
    number_words(g)
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
    hint = "ESC menu (saves)  TAB reset  F2 sound"
    if g.get("category") == "sentences":
        hint += "  ? Merkhilfe"
    if w >= len(hud) + len(hint) + 2:
        safe_add(win, 0, w - len(hint) - 1, hint, curses.color_pair(4))
    banner = g.get("banner")
    if banner and time.time() < banner[1]:
        text = banner[0][:max(0, w - 2)]
        safe_add(win, 1, max(0, (w - len(text)) // 2), text,
                 curses.color_pair(4) | curses.A_BOLD)
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


def put_marked(win, y, x, text, base, hi):
    """Print text where *stars* are highlighted as the memory hooks."""
    for k, part in enumerate(re.split(r"\*(.+?)\*", text)):
        if not part:
            continue
        safe_add(win, y, x, part, hi if k % 2 else base)
        x += len(part)


def wrap_text(s, width):
    lines, cur = [], ""
    for word in s.split():
        if cur and len(cur) + 1 + len(word) > width:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}" if cur else word
    if cur:
        lines.append(cur)
    return lines


def draw_help(win, g, h, w):
    """Merkhilfe overlay for the sentence currently being typed (pauses the game).
    Core sentences show sound-alikes + story; others show a basic card."""
    tgt = sequence_word(g)
    if tgt is None:
        return
    s = MNEMONICS.get(keyof(tgt.de))
    yellow = curses.color_pair(5) | curses.A_BOLD
    normal = curses.color_pair(3)
    dim = curses.color_pair(4)
    bw = min(w - 6, 96)
    if s is not None:
        lines = [(s[0], yellow), (f"= {s[1]}", normal), (f"= {s[2]}", normal), ("", normal)]
        for de, en, ur, sounds in s[3]:
            lines.append((f"  {de:<11} = {en} = {ur}", normal))
            lines.append((f"  {'':11} ~ {' / '.join(sounds)}", yellow))
        lines.append(("", normal))
        lines += [(t, normal) for t in wrap_text(s[4], bw - 4)]
    else:
        ur = tgt.ur_script if USE_URDU_SCRIPT else tgt.ur_roman
        lines = [(tgt.prefix + tgt.de, yellow), (f"= {tgt.en}", normal),
                 (f"= {ur}" if ur else "", normal), ("", normal),
                 ("No sound-alikes for this one yet — Merkhilfe covers the 20 core sentences.", dim)]
    y0 = max(1, (h - len(lines) - 2) // 2)
    x0 = max(0, (w - bw) // 2)
    safe_add(win, y0 - 1, x0, "\u250c" + "\u2500" * (bw - 2) + "\u2510", dim)
    for i, (text, attr) in enumerate(lines):
        put_marked(win, y0 + i, x0 + 2, text, attr, yellow)
    safe_add(win, y0 + len(lines), x0,
             "\u2514" + "\u2500" * (bw - 2) + "\u2518", dim)
    center(win, y0 + len(lines) + 1, "any key: back to the game", dim)


def run_merkhilfe(win, mode):
    """Run the standalone memory trainer, then hand the terminal back to curses.
    endwin() drops the window's nodelay/keypad state, so they are restored here —
    otherwise get_wch() blocks and the menu never redraws."""
    try:
        import merkhilfe
    except ImportError:
        return
    curses.def_prog_mode()
    curses.endwin()
    try:
        (merkhilfe.quiz if mode == "quiz" else merkhilfe.learn)()
    except (EOFError, KeyboardInterrupt):
        pass
    finally:
        curses.reset_prog_mode()
        curses.flushinp()
        win.nodelay(True)
        win.keypad(True)
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        win.clear()
        win.refresh()


def menu_items(urdu, speed, cat, saved, speaker, sent_count, merkhilfe):
    """Menu rows as (id, label, value, adjustable), in display order."""
    rows = []
    if saved:
        rows.append(("continue", "Continue", save_summary(saved), False))
    rows.append(("new", "New game", "", False))
    rows.append(("sentences", "Sentences", f"{sent_count} phrases", False))
    rows.append(("merkhilfe", "Merkhilfe", merkhilfe, True))
    rows.append(("category", "Category", cat, True))
    rows.append(("urdu", "Urdu script", "script" if urdu else "roman", False))
    rows.append(("speed", "Start speed", f"{speed:.2f}x", True))
    sound = "ON" if speaker.enabled else "OFF"
    if not speaker.available:
        sound += "  (no audio tool)"
    rows.append(("sound", "Sound", sound, False))
    rows.append(("quit", "Quit", "", False))
    return rows


def draw_menu(win, h, w, rows, sel, last):
    win.erase()
    gold = curses.color_pair(5) | curses.A_BOLD
    dim = curses.color_pair(4)
    normal = curses.color_pair(3)
    picked = curses.color_pair(1) | curses.A_REVERSE | curses.A_BOLD

    shown = [(r[1], f"\u2039 {r[2]} \u203a" if r[3] else r[2]) for r in rows]
    label_w = max(len(label) for label, _ in shown)
    value_w = max(len(value) for _, value in shown)
    block_w = label_w + value_w + 4          # marker + gap + padding
    left = max(0, (w - block_w) // 2)
    y = max(1, (h - (len(rows) + 9)) // 2)

    center(win, y, "W O R T F A L L", gold)
    center(win, y + 1, "German = English = Urdu", dim)
    for i, (label, value) in enumerate(shown):
        text = ("> " if i == sel else "  ") + label
        text += " " * (block_w - len(text) - len(value)) + value
        safe_add(win, y + 3 + i, left, text, picked if i == sel else normal)
    center(win, y + 4 + len(rows),
           "\u2191\u2193 select   \u2190\u2192 change   ENTER choose   Q quit", dim)
    center(win, y + 5 + len(rows),
           "Type words in number order: 1, 2, 3 ...", dim)
    if last:
        center(win, y + 7 + len(rows), last, curses.color_pair(6))
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
    sel = 0
    merkhilfe_mode = "learn"
    cats = load_pool()
    names = [n for n in cats if n != "sentences"]
    sent_count = len(cats.get("sentences", []))
    cat_i = 0
    g = None  # None = menu
    saved = read_save()
    last = time.time()
    last_save = last
    autosave = config.CONFIG["autosave_seconds"]
    while True:
        h, w = stdscr.getmaxyx()
        now = time.time()
        dt = min(now - last, 0.1)
        last = now
        try:
            while True:
                ch = stdscr.get_wch()
                if g is None:
                    rows = menu_items(
                        USE_URDU_SCRIPT, start_speed,
                        f"{cat_label(names[cat_i])} ({len(cats[names[cat_i]])})",
                        saved, audio.get_speaker(), sent_count, merkhilfe_mode)
                    sel %= len(rows)
                    item = rows[sel][0]
                    key = ch.lower() if isinstance(ch, str) else ch

                    if key in (curses.KEY_UP, "k"):
                        sel = (sel - 1) % len(rows)
                    elif key in (curses.KEY_DOWN, "j"):
                        sel = (sel + 1) % len(rows)
                    elif key in (curses.KEY_LEFT, "h"):
                        if item == "category":
                            cat_i = (cat_i - 1) % len(names)
                        elif item == "speed":
                            start_speed = max(0.25, round(start_speed - 0.25, 2))
                        elif item == "merkhilfe":
                            merkhilfe_mode = "quiz" if merkhilfe_mode == "learn" else "learn"
                        elif item == "urdu":
                            USE_URDU_SCRIPT = not USE_URDU_SCRIPT
                        elif item == "sound":
                            audio.get_speaker().toggle()
                    elif key in (curses.KEY_RIGHT, "l"):
                        if item == "category":
                            cat_i = (cat_i + 1) % len(names)
                        elif item == "speed":
                            start_speed = min(3.0, round(start_speed + 0.25, 2))
                        elif item == "merkhilfe":
                            merkhilfe_mode = "quiz" if merkhilfe_mode == "learn" else "learn"
                        elif item == "urdu":
                            USE_URDU_SCRIPT = not USE_URDU_SCRIPT
                        elif item == "sound":
                            audio.get_speaker().toggle()
                    elif key in ("\n", "\r", curses.KEY_ENTER, " "):
                        if item == "quit":
                            return
                        if item == "continue":
                            game, cat = restore_game(saved, cats)
                            if game is not None:
                                g = game
                                if cat in names:
                                    cat_i = names.index(cat)
                                start_speed = g["speed"]
                            else:
                                g = new_game(cats[names[cat_i]])
                                g["category"] = names[cat_i]
                                g["speed"] = start_speed
                                save_game(g)
                        elif item == "new":
                            g = new_game(cats[names[cat_i]])
                            g["category"] = names[cat_i]
                            g["speed"] = start_speed
                            save_game(g)
                        elif item == "sentences":
                            g = new_game(cats["sentences"])
                            g["category"] = "sentences"
                            g["speed"] = start_speed
                            save_game(g)
                        elif item == "merkhilfe":
                            run_merkhilfe(stdscr, merkhilfe_mode)
                        elif item == "category":
                            cat_i = (cat_i + 1) % len(names)
                        elif item == "speed":
                            start_speed = min(3.0, round(start_speed + 0.25, 2))
                        elif item == "urdu":
                            USE_URDU_SCRIPT = not USE_URDU_SCRIPT
                        elif item == "sound":
                            audio.get_speaker().toggle()
                        if g is not None:
                            g["last_spawn"] = now
                            theme = g["killed"] // BG_EVERY
                            apply_theme(stdscr, theme)
                            last_save = now
                    elif key == "n":
                        g = new_game(cats[names[cat_i]])
                        g["category"] = names[cat_i]
                        g["speed"] = start_speed
                        g["last_spawn"] = now
                        theme = 0
                        apply_theme(stdscr, 0)
                        save_game(g)
                        last_save = now
                    elif key == "s":
                        g = new_game(cats["sentences"])
                        g["category"] = "sentences"
                        g["speed"] = start_speed
                        g["last_spawn"] = now
                        theme = 0
                        apply_theme(stdscr, 0)
                        save_game(g)
                        last_save = now
                    elif key in ("q", "\x1b"):
                        return
                    elif ch == curses.KEY_F0 + 2 or key == "m":
                        audio.get_speaker().toggle()
                    elif key == "c":
                        cat_i = (cat_i + 1) % len(names)
                    elif key == "u":
                        USE_URDU_SCRIPT = not USE_URDU_SCRIPT
                    elif key in ("+", "="):
                        start_speed = min(3.0, round(start_speed + 0.25, 2))
                    elif key in ("-", "_"):
                        start_speed = max(0.25, round(start_speed - 0.25, 2))
                    continue
                if g.get("help"):
                    g["help"] = False
                elif ch == "?":
                    if sequence_word(g) is not None:
                        g["help"] = True
                elif ch == "\x1b":
                    last_result = (f"Last game: score {g['score']}  correct {g['killed']}"
                                   f"  missed {g['missed']}  best combo {g['best_combo']}"
                                   f"  (saved)")
                    save_game(g)
                    saved = read_save()
                    start_speed = g["speed"]
                    g = None
                    sel = 0
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
        if g is not None and now - last_save >= autosave:
            save_game(g)
            last_save = now
        if g is None:
            rows = menu_items(
                USE_URDU_SCRIPT, start_speed,
                f"{cat_label(names[cat_i])} ({len(cats[names[cat_i]])})",
                saved, audio.get_speaker(), sent_count, merkhilfe_mode)
            sel %= len(rows)
            draw_menu(stdscr, h, w, rows, sel, last_result)
        else:
            if g.get("help"):
                draw_help(stdscr, g, h, w)   # paused: no update, no word movement
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
