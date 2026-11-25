"""Curses renderer: Dracula theme, per-language styled falling words,
danger-zone band, solved/missed animations, article-coloured hints,
boxed overlays. Merges the v2 language features with the v1 game UI.
"""
import curses
import time

import audio
import sfx
import theme
from textnorm import article_of
from theme import color, display_width
from word import WordState

URDU_SHAPED = False   # toggled with the U key in the menu; see theme.urdu_text

PAIR_DANGER = 20      # red on dark-red, the danger-zone band

# classic German-learning convention: der=blue, die=red, das=green
ARTICLE_COLORS = {"der": "cyan", "die": "red", "das": "green"}

SOLVED_FRAMES = ("✶", "✷", "❋", "·")
MISSED_FRAMES = ("✗", "✗", "✗", "·")


def init_colors(stdscr=None):
    if stdscr is None:
        stdscr = curses.initscr()
    theme.init_theme(stdscr)
    if curses.has_colors() and theme.PAIRS:
        table = theme.DRACULA if curses.COLORS >= 256 else theme.FALLBACK
        try:
            curses.init_pair(PAIR_DANGER, table["red"], table["bg"])
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


def draw_word(stdscr, word, y, is_target, urgent, height, width):
    """[ German == English == Urdu ] - each language has its own colour and style."""
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

    put("[ ", frame)
    for i, text in enumerate(parts):
        if i == 2:
            text = theme.urdu_text(text, URDU_SHAPED)
        elif urgent:
            text = text.upper()
        attr = color(cols[i % 3]) | styles[i % 3]
        if i == 0 and urgent:
            attr = color("red") | curses.A_BOLD | curses.A_BLINK
        if is_target and i == 0:
            attr |= curses.A_UNDERLINE
        put(text, attr)
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


def _danger_band(stdscr, h, w, danger_rows):
    for row in range(max(2, h - 4 - danger_rows), h - 4):
        safe_add(stdscr, row, 0, "·" * (w - 1), color("red") | curses.A_DIM)


def _article_hint(target):
    if target.entry.get("pos") != "noun" or target.answer.count(" ") < 1:
        return None
    art = article_of(target.answer)
    if art and art in ARTICLE_COLORS:
        return art
    return None


def draw(stdscr, state, mode="playing", high_score=0, category_label="All"):
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
            "██     ██  ██████  ██████  ███████ ████████ ███████",
            "██     ██ ██    ██ ██   ██ ██         ██    ██     ",
            "██  █  ██ ██    ██ ██████  █████      ██    ███████",
            "██ ███ ██ ██    ██ ██   ██ ██         ██    ██     ",
            " ███ ███   ██████  ██   ██ ███████    ██    ███████",
        ]
        for i, line in enumerate(banner):
            centered(stdscr, 1 + i, line, title)
        centered(stdscr, 7, "German A1 falling-word typing game", color("cyan"))
        centered(stdscr, 8, "[ Hallo == Hello == ہیلو ]", color("green") | curses.A_BOLD)
        centered(stdscr, 10, f"High score: {high_score}", color("yellow"))
        centered(stdscr, 12, "[ ENTER ]  START GAME", color("green") | curses.A_BOLD)
        centered(stdscr, 14, f"[ C ] Category: {category_label}", color("fg"))
        centered(stdscr, 15, f"[ A ] Articles: {state.articles_mode}    [ P ] Plurals: {'ON' if state.plural_mode else 'OFF'}", color("fg"))
        centered(stdscr, 16, f"[ L ] Learn mode    [ U ] Urdu display: {'shaped' if URDU_SHAPED else 'raw'}", color("fg"))
        centered(stdscr, 17, f"[ F2 ] {audio.get_speaker().label()}    [ F3 ] {sfx.get_sfx().label()}", color("orange"))
        centered(stdscr, 18, "[ ESC ] [ ESC ] Exit", color("comment"))
        centered(stdscr, 21, "Type the German word. Correct answers are accepted instantly and spoken aloud.", color("comment"))
    elif mode == "paused":
        box_w = 46
        top = max(2, h // 2 - 3)
        left = max(0, (w - box_w) // 2)
        safe_add(stdscr, top, left, "┌" + "─" * box_w + "┐", title)
        centered(stdscr, top + 1, "P A U S E D", title)
        centered(stdscr, top + 2, "[ESC] Resume    [ESC][ESC] Save & exit", color("fg"))
        centered(stdscr, top + 3, "[Q] Save and quit", color("fg"))
        safe_add(stdscr, top + 5, left, "└" + "─" * box_w + "┘", title)
    elif mode == "summary":
        s = state.summary()
        centered(stdscr, 2, "═══════  SESSION SUMMARY  ═══════", title)
        rows = [f"Score: {s['score']}   High score: {high_score}", f"Level reached: {s['level']}",
                f"Correct: {s['correct']}   Mistakes: {s['mistakes']}",
                f"Accuracy: {s['accuracy']:.0f}%   Words seen: {s['words_seen']}"]
        for i, line in enumerate(rows):
            safe_add(stdscr, 5 + i, 20, line, color("cyan"))
        safe_add(stdscr, 11, 20, "Words to review:", color("pink") | curses.A_BOLD)
        for i, (de, count) in enumerate(s["missed"][:7]):
            entry = next((v for v in state.all_vocab if v["de"] == de), {})
            safe_add(stdscr, 12 + i, 22, f"{de} ({entry.get('en','?')}) x{count}", color("orange"))
        safe_add(stdscr, 21, 20, "[Enter] Play again   [M] Menu   [Q] Quit", color("green"))
    else:
        lives_text = "∞" if state.infinite_lives else "♥" * state.lives
        sep = color("comment")
        level_note = f" ({state.correct_count % 10}/10)"
        streak_note = " ▲▲" if state.streak >= 5 else ""
        header = [(" WORTFALL ", title), ("│ ", sep),
                  (f"SCORE {state.score} ", color("green") | curses.A_BOLD), ("│ ", sep),
                  (f"LIVES {lives_text} ", color("red") | curses.A_BOLD), ("│ ", sep),
                  (f"LEVEL {state.level}{level_note} ", color("cyan") | curses.A_BOLD), ("│ ", sep),
                  (f"STREAK {state.streak}{streak_note}", color("orange") | curses.A_BOLD)]
        x = 0
        for text, attr in header:
            safe_add(stdscr, 0, x, text, attr)
            x += display_width(text)
        hline(stdscr, 1, w, sep)
        hline(stdscr, h - 4, w, sep)
        _danger_band(stdscr, h, w, 2)
        active = sorted([x for x in state.words if x.state == WordState.FALLING], key=lambda x: x.y, reverse=True)
        for word in state.words:
            if word.state == WordState.FALLING:
                target = bool(active) and word is active[0]
                urgent = word.elapsed_fraction() >= .9
                draw_word(stdscr, word, int(word.y) + 2, target, urgent, h, w)
            elif word.state in (WordState.SOLVED, WordState.MISSED):
                draw_effect(stdscr, word, h, w)
        hint = ""
        if active:
            target = active[0]
            frac = target.elapsed_fraction()
            if frac >= .75 and target.entry["pos"] == "noun":
                art = _article_hint(target)
                if art:
                    hint = f"Hint: {art} ___"
                else:
                    hint = f"Hint: {target.answer.split()[0]} ___"
            elif frac >= .5:
                hint = f"Hint: {target.answer[0]}..."
        mode_text = "LEARN MODE" if state.learn_mode else f"LIVES {lives_text}"
        sp = audio.get_speaker()
        safe_add(stdscr, h - 3, 1,
                 f" SPEED [ - ] {state.speed_scale:.2f}x [ + ]   [ TAB ] INFINITE LIVES: {'ON' if state.infinite_lives else 'OFF'}   [ F2 ] {sp.label()}   [ F3 ] {sfx.get_sfx().label()}",
                 color("purple") | curses.A_BOLD)
        if state.feedback and time.monotonic() < state.feedback_until:
            good = state.feedback.startswith(("+", "LEVEL"))
            safe_add(stdscr, h - 2, 1, state.feedback,
                     color("green" if good else "red") | curses.A_BOLD)
        else:
            safe_add(stdscr, h - 2, 1, "[ ESC ] pause    Type German; auto-correct on final letter", color("comment"))
        safe_add(stdscr, h - 1, 1, "TYPE: ", color("pink") | curses.A_BOLD)
        safe_add(stdscr, h - 1, 7, f"{state.input_buffer}_", color("fg") | curses.A_BOLD)
        safe_add(stdscr, h - 1, 9 + len(state.input_buffer), f" {hint}  [{mode_text}]", color("yellow"))
    stdscr.refresh()
