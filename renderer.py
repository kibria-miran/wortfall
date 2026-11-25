"""Curses renderer: clean minimal UI, time-animated background (stars, birds,
weather), blinking English/Urdu text, article-coloured hints and effects."""
import curses
import math
import random
import time

import audio
import sfx
import theme
from config import CONFIG
from textnorm import article_of
from theme import color, display_width
from word import WordState

URDU_SHAPED = False   # toggled with the U key in the menu; see theme.urdu_text

# classic German-learning convention: der=blue, die=red, das=green
ARTICLE_COLORS = {"der": "cyan", "die": "red", "das": "green"}

SOLVED_FRAMES = ("✶", "✷", "❋", "·")
MISSED_FRAMES = ("✗", "✗", "✗", "·")

WEATHERS = ("clear", "cloudy", "rain", "snow")


class Background:
    """Procedural, purely time-based sky: twinkling stars, flying birds and a
    slowly cycling weather (clear → cloudy → rain → snow). No game state."""
    def __init__(self):
        rng = random.Random(365303)
        self.stars = [(rng.random(), rng.random(), rng.random()) for _ in range(70)]
        self.birds = [(rng.random(), 0.05 + rng.random() * 0.12, 5.0 + rng.random() * 4.0,
                       1 if rng.getrandbits(1) else -1) for _ in range(3)]
        self.rain = [(rng.random(), rng.random()) for _ in range(16)]
        self.flakes = [(rng.random(), rng.random()) for _ in range(14)]
        self.clouds = [(rng.random(), 0.04 + rng.random() * 0.22, 0.8 + rng.random() * 0.7)
                       for _ in range(4)]

    def weather(self, t):
        return WEATHERS[int(t / CONFIG["weather_cycle"]) % len(WEATHERS)]

    def draw(self, stdscr, h, w, t):
        put = safe_add
        dim = color("comment") | curses.A_DIM
        faint = color("fg") | curses.A_DIM
        top, bottom = 2, h - 5
        if top > bottom:
            return
        span = bottom - top + 1
        weather = self.weather(t)

        if weather == "clear":
            for i, (nx, ny, tw) in enumerate(self.stars):
                if ((t * 0.8 + tw) % 1.0) > 0.72:      # each star on ~72% of the time
                    x = 1 + int(nx * (w - 3))
                    y = top + int(ny * (span - 1))
                    glyph = "·" if tw > 0.5 else "+"
                    put(stdscr, y, x, glyph, faint)
        elif weather == "cloudy":
            for i, (nx, ny, tw) in enumerate(self.stars[:24]):
                if ((t * 0.5 + tw) % 1.0) > 0.85:
                    x = 1 + int(nx * (w - 3)); y = top + int(ny * (span - 1))
                    put(stdscr, y, x, "·", faint)
            self._clouds(stdscr, h, w, t, dim)
        elif weather == "rain":
            self._clouds(stdscr, h, w, t, dim, drops=True)
            for i, (nx, off) in enumerate(self.rain):
                x = 1 + int(nx * (w - 3))
                y = top + int((off + t * 1.6) % 1.0 * (span - 1))
                put(stdscr, y, x, "/", color("cyan") | curses.A_DIM)
        elif weather == "snow":
            for i, (nx, off) in enumerate(self.flakes):
                x = 1 + int((nx + 0.03 * math.sin(t * 1.1 + i)) % 1.0 * (w - 3))
                y = top + int((off + t * 0.35) % 1.0 * (span - 1))
                put(stdscr, y, x, "*", faint)

        for i, (ny, v, speed, direction) in enumerate(self.birds):
            if weather in ("rain", "snow"):
                continue
            y = top + int(ny * span)
            flap = int((t * 2.5 + i) / 0.4) % 4
            glyph = ("^v^", "~v~", "~^~", "-v-")[flap]
            travel = (t * speed * direction) % (w + 16)
            x = int(travel) - 8 if direction > 0 else w - 1 - int(travel)
            put(stdscr, y, x, glyph, dim)

    def _clouds(self, stdscr, h, w, t, dim, drops=False):
        shapes = ("  .--~~--.  ", " .~~~~~~~~. ", "  .-~~~-.   ")
        for i, (nx, ny, speed) in enumerate(self.clouds):
            y = 3 + int(ny * 4) + (2 if drops and i == 0 else 0)
            travel = (t * speed + i * 30) % (w + 20)
            x = int(travel) - 12
            safe_add(stdscr, y, x, shapes[i % 3], dim)


BACKGROUND = Background()


def init_colors(stdscr=None):
    if stdscr is None:
        stdscr = curses.initscr()
    import theme
    theme.init_theme(stdscr)
    if curses.has_colors() and theme.PAIRS:
        table = theme.PALETTE if curses.COLORS >= 256 else theme.FALLBACK
        try:
            curses.init_pair(20, table["red"], table["bg"])
        except curses.error:
            pass


def safe_add(stdscr, y, x, s, attr=0):
    h, w = stdscr.getmaxyx()
    if 0 <= y < h and 0 <= x < w:
        s = str(s)
        while s and display_width(s) > max(0, w - x - 1):
            s = s[:-1]
        if not s:
            return
        try:
            stdscr.addstr(y, x, s, attr)
        except (curses.error, UnicodeEncodeError):
            pass


def centered(stdscr, y, text, attr=0):
    h, w = stdscr.getmaxyx()
    safe_add(stdscr, y, max(0, (w - display_width(text)) // 2), text, attr)


def hline(stdscr, y, w, attr):
    safe_add(stdscr, y, 0, "─" * (w - 1), attr)


def _blink_on(word, now):
    period = CONFIG["en_ur_blink"]
    phase = ((now - word.spawn_time) / period) % 2
    return phase < 1


def draw_word(stdscr, word, y, is_target, urgent, height, width, hide_de=False):
    """[ German == English == Urdu ] — German holds steady while the English and
    Urdu flip-flop out of phase: when English is lit Urdu is dark, and vice versa.
    With hide_de (recall mode) the German is not shown: the player types it from
    the meaning."""
    import theme
    parts = list(word.parts) if word.parts else [word.prompt]
    cols = list(word.colors) if word.colors else ["yellow", "cyan", "pink"]
    styles = [theme.STYLE_DE, theme.STYLE_EN, theme.STYLE_UR]
    frame = color("pink") | curses.A_BOLD if is_target else color("comment")
    sep = color("comment")
    x = word.x

    def put(text, attr):
        nonlocal x
        if x + display_width(text) > width - 1:
            return
        safe_add(stdscr, y, x, text, attr)
        x += display_width(text)

    def shape(i, text):
        if i == 2:
            return theme.urdu_text(text, URDU_SHAPED)
        return text.upper() if urgent else text

    put("[ ", frame)
    for i, text in enumerate(parts):
        on = True
        if hide_de and i == 0:
            on = False
        elif i > 0:
            blink = _blink_on(word, time.monotonic())
            on = blink if i == 1 else not blink
        shown = shape(i, text)
        attr = color(cols[i % 3]) | styles[i % 3]
        if i == 0 and urgent:
            attr = color("red") | curses.A_BOLD | curses.A_BLINK
        if is_target and i == 0:
            attr |= curses.A_UNDERLINE
        if on:
            put(shown, attr)
        else:
            put(" " * display_width(shown), color("fg"))
        if i < len(parts) - 1:
            put(" == ", sep)
    put(" ]", frame)


def draw_effect(stdscr, word, height, width):
    """Solved = green burst; missed = the correct answer lingers in red."""
    if word.resolve_time is None:
        return
    frame = word.explosion_frame() or 0
    y = min(int(word.y) + 2, height - 5)
    if word.state == WordState.SOLVED:
        safe_add(stdscr, y, word.x, SOLVED_FRAMES[frame],
                 color("green") | curses.A_BOLD)
    else:
        text = f"✗  {word.answer} = {word.entry.get('en', '?')}"
        attr = color("red") | curses.A_BOLD
        if frame >= 2:
            attr = color("red") | curses.A_DIM
        safe_add(stdscr, y, word.x, text, attr)


def _article_hint(target):
    if target.entry.get("pos") != "noun" or target.answer.count(" ") < 1:
        return None
    art = article_of(target.answer)
    if art and art in ARTICLE_COLORS:
        return art
    return None


def _header(stdscr, state, w):
    sep = color("comment")
    lives = "∞" if state.infinite_lives else "♥" * max(state.lives, 0)
    cells = [("WORTFALL", color("purple") | curses.A_BOLD),
             (f"SCORE {state.score}", color("green") | curses.A_BOLD),
             (lives, color("red") | curses.A_BOLD),
             (f"LV {state.level}", color("cyan") | curses.A_BOLD)]
    if state.streak >= 2:
        cells.append((f"×{state.streak}", color("orange") | curses.A_BOLD))
    if state.learn_mode:
        cells.append(("LEARN", color("pink") | curses.A_BOLD))
    x = 1
    for i, (text, attr) in enumerate(cells):
        if i:
            safe_add(stdscr, 0, x, "·", sep); x += 2
        safe_add(stdscr, 0, x, text, attr)
        x += display_width(text) + 1


def draw(stdscr, state, mode="playing", high_score=0, category_label="All"):
    import theme
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    title = color("purple") | curses.A_BOLD
    if h < 24 or w < 80:
        safe_add(stdscr, max(0, h // 2), 1, "Please enlarge terminal to at least 80x24", color("orange"))
        safe_add(stdscr, max(0, h // 2 + 1), 1, "The game is paused until the terminal is large enough.", color("comment"))
        stdscr.refresh()
        return
    if mode == "menu":
        banner = [
            "██     ██  ██████  ██████  ███████ ████████ ██████",
            "██     ██ ██    ██ ██   ██ ██         ██    ██     ",
            "██  █  ██ ██    ██ ██████  ██████     ██    ███████",
            "██ ███ ██ ██    ██ ██   ██ ██         ██    ██     ",
            " ███ ███   ██████  ██   ██ ███████    ██    ███████",
        ]
        now = time.monotonic()
        for i, line in enumerate(banner):
            centered(stdscr, 1 + i, line, title)
        centered(stdscr, 7, "German A1 falling-word typing game", color("cyan"))
        sample = [("der Baum", color("yellow") | curses.A_BOLD, 10),
                  ("tree", color("cyan") | theme.STYLE_EN, 4),
                  ("درخت", color("pink"), 4)]
        total = display_width("[ ") + sum(disp + 4 for _, _, disp in sample) - 4 + display_width(" ]")
        sx = (w - total) // 2
        blink_off = int(now / 0.5) % 2 == 1
        safe_add(stdscr, 9, sx, "[ ", color("comment")); sx += 2
        for i, (text, attr, disp) in enumerate(sample):
            safe_add(stdscr, 9, sx, " " * disp if blink_off and i else text, attr)
            sx += disp
        safe_add(stdscr, 9, sx, " ]", color("comment"))
        centered(stdscr, 10, "English/Urdu flip-flop · type the German word", color("comment"))
        centered(stdscr, 12, f"High score: {high_score}", color("yellow"))
        centered(stdscr, 14, "[ ENTER ]  START          [ L ] LEARN MODE", color("green") | curses.A_BOLD)
        centered(stdscr, 15, f"[ C ] Category: {category_label}    [ A ] Articles: {state.articles_mode}    [ P ] Plurals: {'ON' if state.plural_mode else 'OFF'}", color("fg"))
        centered(stdscr, 16, f"[ R ] Recall: {'ON (type German from meaning)' if state.recall_mode else 'OFF'}", color("cyan"))
        centered(stdscr, 17, f"[ W ] Weak-word review: {'ON' if state.weighted else 'OFF (pure random)'}", color("fg"))
        centered(stdscr, 18, f"[ U ] Urdu: {'shaped' if URDU_SHAPED else 'raw'}    [ F2 ] {audio.get_speaker().label()}    [ F3 ] {sfx.get_sfx().label()}", color("orange"))
        centered(stdscr, 19, "In game:  SPACE clears typing · +/- speed · TAB infinite lives", color("comment"))
        centered(stdscr, 20, "German letters: ä=ae  ö=oe  ü=ue  ß=ss · '?' skips in learn mode", color("comment"))
        centered(stdscr, 21, "ESC ESC — exit", color("comment"))
        if state.feedback and time.monotonic() < state.feedback_until:
            centered(stdscr, 22, state.feedback, color("orange") | curses.A_BOLD)
    elif mode == "paused":
        box_w = 42
        top = max(2, h // 2 - 3)
        left = max(0, (w - box_w) // 2)
        safe_add(stdscr, top, left, "┌" + "─" * box_w + "┐", title)
        centered(stdscr, top + 1, "P A U S E D", title)
        centered(stdscr, top + 3, "any key resume  ·  Q save & quit", color("fg"))
        safe_add(stdscr, top + 5, left, "└" + "─" * box_w + "┘", title)
    elif mode == "summary":
        s = state.summary()
        centered(stdscr, 2, "═══════  SESSION SUMMARY  ═══════", title)
        rows = [f"Score: {s['score']}   High score: {high_score}", f"Level reached: {s['level']}",
                f"Correct: {s['correct']}   Mistakes: {s['mistakes']}",
                f"Accuracy: {s['accuracy']:.0f}%   Words seen: {s['words_seen']}"]
        for i, line in enumerate(rows):
            safe_add(stdscr, 5 + i, 24, line, color("cyan"))
        safe_add(stdscr, 11, 24, "Words to review:", color("pink") | curses.A_BOLD)
        for i, (de, count) in enumerate(s["missed"][:7]):
            entry = next((v for v in state.all_vocab if v["de"] == de), {})
            safe_add(stdscr, 12 + i, 26, f"{de} ({entry.get('en','?')}) x{count}", color("orange"))
        safe_add(stdscr, 21, 24, "[Enter] Play again   [M] Menu   [Q] Quit", color("green"))
    else:
        _header(stdscr, state, w)
        sep = color("comment")
        hline(stdscr, 1, w, sep)
        hline(stdscr, h - 4, w, sep)
        BACKGROUND.draw(stdscr, h, w, time.monotonic())
        active = sorted([x for x in state.words if x.state == WordState.FALLING],
                        key=lambda x: x.y, reverse=True)
        for word in state.words:
            if word.state == WordState.FALLING:
                target = bool(active) and word is active[0]
                urgent = word.elapsed_fraction() >= .9
                draw_word(stdscr, word, int(word.y) + 2, target, urgent, h, w,
                          hide_de=state.recall_mode and not state.learn_mode)
                note = word.entry.get("note")
                if state.learn_mode and note:
                    safe_add(stdscr, int(word.y) + 3, word.x, f"ℹ {note}",
                             color("comment") | curses.A_DIM)
            elif word.state in (WordState.SOLVED, WordState.MISSED):
                draw_effect(stdscr, word, h, w)
        hint = ""
        if active:
            target = active[0]
            frac = target.elapsed_fraction()
            note = target.entry.get("note")
            if frac >= .75:
                if note:
                    hint = f"ℹ {note}"
                elif target.entry["pos"] == "noun":
                    art = _article_hint(target)
                    hint = f"hint: {art} ___" if art else f"hint: {target.answer.split()[0]} ___"
                else:
                    hint = f"hint: {target.answer[0]}…"
            elif frac >= .5:
                hint = f"hint: {target.answer[0]}…"
        safe_add(stdscr, h - 3, 1, hint, color("yellow"))
        right = f"F2 {audio.get_speaker().label()} · F3 {sfx.get_sfx().label()}"
        safe_add(stdscr, h - 3, max(1, w - display_width(right) - 2), right, color("comment") | curses.A_DIM)
        if state.feedback and time.monotonic() < state.feedback_until:
            good = state.feedback.startswith(("+", "LEVEL"))
            safe_add(stdscr, h - 2, 1, state.feedback,
                     color("green" if good else "red") | curses.A_BOLD)
        else:
            safe_add(stdscr, h - 2, 1, "type German · SPACE resets · ESC pauses", color("comment") | curses.A_DIM)
        safe_add(stdscr, h - 1, 1, "▸ ", color("pink") | curses.A_BOLD)
        safe_add(stdscr, h - 1, 3, f"{state.input_buffer}_", color("fg") | curses.A_BOLD)
    stdscr.refresh()
