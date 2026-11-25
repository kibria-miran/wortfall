"""Curses rendering: layout, colors, falling words, HUD, screens."""

import curses
import time

from config import CONFIG

# color pair ids
P_HEADER = 1        # black on cyan
P_WORD = 2          # yellow on black
P_DANGER = 3        # red on black (word in danger zone)
P_INPUT = 4         # white on blue
P_GOOD = 5          # green on black
P_BAD = 6           # red on black
P_ART_DER = 7       # cyan on black
P_ART_DIE = 8       # magenta on black
P_ART_DAS = 9       # green on black
P_NEUTRAL = 10      # white on black
P_DANGER_ZONE = 11  # danger zone background band


def init_colors(stdscr):
    curses.start_color()
    try:
        curses.use_default_colors()
        bg = -1
    except curses.error:
        bg = curses.COLOR_BLACK

    curses.init_pair(P_HEADER, curses.COLOR_BLACK, curses.COLOR_CYAN)
    curses.init_pair(P_WORD, curses.COLOR_YELLOW, bg)
    curses.init_pair(P_DANGER, curses.COLOR_RED, bg)
    curses.init_pair(P_INPUT, curses.COLOR_WHITE, curses.COLOR_BLUE)
    curses.init_pair(P_GOOD, curses.COLOR_GREEN, bg)
    curses.init_pair(P_BAD, curses.COLOR_RED, bg)
    curses.init_pair(P_ART_DER, curses.COLOR_CYAN, bg)
    curses.init_pair(P_ART_DIE, curses.COLOR_MAGENTA, bg)
    curses.init_pair(P_ART_DAS, curses.COLOR_GREEN, bg)
    curses.init_pair(P_NEUTRAL, curses.COLOR_WHITE, bg)
    curses.init_pair(P_DANGER_ZONE, curses.COLOR_RED, bg)


def article_attr(article):
    if not CONFIG["article_color_coding"]:
        return curses.color_pair(P_NEUTRAL)
    a = article.lower()
    if a == "der":
        return curses.color_pair(P_ART_DER) | curses.A_BOLD
    if a == "die":
        return curses.color_pair(P_ART_DIE) | curses.A_BOLD
    if a == "das":
        return curses.color_pair(P_ART_DAS) | curses.A_BOLD
    return curses.color_pair(P_NEUTRAL)


def compute_layout(stdscr):
    height, width = stdscr.getmaxyx()
    pf_top = 1
    pf_bottom = max(pf_top + 3, height - 5)
    return {
        "height": height,
        "width": width,
        "pf_top": pf_top,
        "pf_bottom": pf_bottom,
        "play_height": pf_bottom - pf_top + 1,
    }


def _addstr(stdscr, y, x, text, attr=0):
    height, width = stdscr.getmaxyx()
    if y < 0 or y >= height or x >= width:
        return
    if x + len(text) > width:
        text = text[: max(0, width - x)]
    if not text:
        return
    try:
        stdscr.addstr(y, x, text, attr)
    except curses.error:
        pass


def draw_centered(stdscr, y, text, attr=0):
    _, width = stdscr.getmaxyx()
    x = max(0, (width - len(text)) // 2)
    _addstr(stdscr, y, x, text, attr)


def draw_game(stdscr, state, layout):
    height, width = layout["height"], layout["width"]
    pf_top, pf_bottom = layout["pf_top"], layout["pf_bottom"]
    play_height = layout["play_height"]

    stdscr.erase()

    # header bar
    hearts = "♥" * state.lives + "·" * max(0, CONFIG["max_lives"] - state.lives)
    header = " SCORE: %d   LIVES: %s   LEVEL: %d   STREAK: x%d " % (
        state.score, hearts, state.level, state.streak,
    )
    if state.streak >= 5:
        header += "  >>"
    header += " " * max(0, width - len(header) - 1)
    _addstr(stdscr, 0, 0, header[:width], curses.color_pair(P_HEADER) | curses.A_BOLD)

    # danger zone: bottom rows of the play field
    for row in range(max(pf_top, pf_bottom - CONFIG["danger_rows"] + 1), pf_bottom + 1):
        _addstr(stdscr, row, 0, " " * width, curses.color_pair(P_DANGER_ZONE))

    # falling words + explosion animation
    target = state.target_word()
    now = time.time()
    for word in state.words:
        row = pf_top + int(word.y)
        text = "[ %s ]" % word.en
        x = min(word.x, max(1, width - len(text) - 1))

        if word.exploding:
            frame = word.explosion_frame(now) or "*"
            _addstr(stdscr, row, x, frame, curses.color_pair(P_GOOD) | curses.A_BOLD)
            continue

        if word is target:
            attr = curses.color_pair(P_WORD) | curses.A_BOLD
        else:
            attr = curses.color_pair(P_WORD)
        if int(word.y) >= play_height - CONFIG["danger_rows"]:
            attr = curses.color_pair(P_DANGER) | curses.A_BLINK | curses.A_BOLD
        _addstr(stdscr, row, x, text, attr)

    # separator
    sep_row = pf_bottom + 1
    if sep_row < height:
        _addstr(stdscr, sep_row, 0, "─" * width, curses.A_DIM)

    # hint / message line
    msg_row = pf_bottom + 2
    if msg_row < height:
        if state.message and time.time() < state.message_until:
            good = state.message.startswith(("✔", "★", "♥"))
            attr = curses.color_pair(P_GOOD if good else P_BAD) | curses.A_BOLD
            _addstr(stdscr, msg_row, 0, " " + state.message, attr)
        else:
            _draw_hint(stdscr, msg_row, state)

    # input line
    in_row = min(msg_row + 1, height - 1)
    label = " TYPE: %s_ " % state.input_buffer
    if CONFIG["articles_required"]:
        label += "(with article) "
    _addstr(stdscr, in_row, 0, label, curses.color_pair(P_INPUT) | curses.A_BOLD)

    if state.paused:
        _draw_pause_overlay(stdscr, layout)


def _draw_hint(stdscr, row, state):
    target = state.target_word()
    if target is None:
        _addstr(stdscr, row, 0, " HINT: wait for a word...", curses.color_pair(P_NEUTRAL))
        return
    if CONFIG["articles_required"] and target.article:
        text = ' HINT: full answer with article: '
        _addstr(stdscr, row, 0, text, curses.color_pair(P_NEUTRAL))
        _addstr(stdscr, row, len(text), target.article.lower(),
                article_attr(target.article))
        _addstr(stdscr, row, len(text) + len(target.article),
                " " + target.noun.lower(), curses.color_pair(P_NEUTRAL))
        return
    if target.article:
        prefix = ' HINT: "%s" → ' % target.en
        _addstr(stdscr, row, 0, prefix, curses.color_pair(P_NEUTRAL))
        _addstr(stdscr, row, len(prefix), target.article, article_attr(target.article))
        _addstr(stdscr, row, len(prefix) + len(target.article) + 1,
                "___   (article: %s)" % target.gender, curses.color_pair(P_NEUTRAL))
        return
    _addstr(stdscr, row, 0, ' HINT: German for "%s" starts with "%s"' % (
        target.en, target.noun[0].lower()), curses.color_pair(P_NEUTRAL))


def _draw_pause_overlay(stdscr, layout):
    height, _ = layout["height"], layout["width"]
    top = max(1, height // 2 - 2)
    lines = [
        "┌" + "─" * 38 + "┐",
        "│            P A U S E D              │",
        "│  ESC / P resume   Q quit to menu    │",
        "└" + "─" * 38 + "┘",
    ]
    for i, line in enumerate(lines):
        draw_centered(stdscr, top + i, line, curses.A_REVERSE)


def draw_menu(stdscr, articles_required, category, high_score):
    stdscr.erase()
    height, _ = stdscr.getmaxyx()

    title = [
        "██     ██  ██████  ██████  ███████ ████████ ███████",
        "██     ██ ██    ██ ██   ██ ██         ██    ██     ",
        "██  █  ██ ██    ██ ██████  █████      ██    ███████",
        "██ ███ ██ ██    ██ ██   ██ ██         ██    ██     ",
        " ███ ███   ██████  ██   ██ ███████    ██    ███████",
    ]
    y = max(1, height // 2 - 8)
    for i, line in enumerate(title):
        draw_centered(stdscr, y + i, line, curses.color_pair(P_WORD) | curses.A_BOLD)

    y += len(title) + 1
    draw_centered(stdscr, y, "German A1 — type the German word before it falls!", curses.A_DIM)
    y += 2
    draw_centered(stdscr, y, "► ENTER: start        [category: %s]" % category)
    y += 1
    draw_centered(stdscr, y, "► C: choose category   A: articles %s" % (
        "ON " if articles_required else "OFF",
    ))
    y += 1
    draw_centered(stdscr, y, "► High score: %d" % high_score)
    y += 1
    draw_centered(stdscr, y, "► Q: quit")
    y += 2
    draw_centered(stdscr, y,
                  "In game: ESC pause · ENTER submit · backspace edit · type ae/oe/ue/ss",
                  curses.A_DIM)
    stdscr.refresh()


def draw_category_select(stdscr, cats, current, all_count):
    stdscr.erase()
    height, _ = stdscr.getmaxyx()
    draw_centered(stdscr, 1, "── SELECT CATEGORY ──",
                  curses.color_pair(P_HEADER) | curses.A_BOLD)
    draw_centered(stdscr, 2, "0. all words (%d)" % all_count, curses.A_DIM)
    for i, cat in enumerate(cats):
        if 4 + i >= height - 2:
            draw_centered(stdscr, height - 2, "...", curses.A_DIM)
            break
        attr = curses.A_BOLD if cat == current else curses.A_NORMAL
        draw_centered(stdscr, 4 + i, "%2d. %s" % (i + 1, cat), attr)
    draw_centered(stdscr, height - 1,
                  "Number to choose · ESC all words · Q back", curses.A_DIM)
    stdscr.refresh()


def draw_game_over(stdscr, summary, high_score, new_high):
    stdscr.erase()
    height, _ = stdscr.getmaxyx()

    y = max(1, height // 2 - 9)
    draw_centered(stdscr, y, "═══════  G A M E   O V E R  ═══════",
                  curses.color_pair(P_BAD) | curses.A_BOLD)
    y += 2
    draw_centered(stdscr, y, "Score: %d        Level reached: %d" % (
        summary["score"], summary["level"]))
    y += 1
    draw_centered(stdscr, y, "Correct: %d    Mistakes: %d    Escaped: %d" % (
        summary["correct"], summary["mistakes"], summary["escaped"]))
    y += 1
    draw_centered(stdscr, y, "Unique words seen: %d    Best streak: x%d" % (
        summary["unique_words"], summary["best_streak"]))
    y += 1
    if new_high:
        draw_centered(stdscr, y, "★ NEW HIGH SCORE: %d ★" % high_score,
                      curses.color_pair(P_GOOD) | curses.A_BOLD)
    else:
        draw_centered(stdscr, y, "High score: %d" % high_score, curses.A_DIM)
    y += 2
    draw_centered(stdscr, y, "Words needing review:",
                  curses.color_pair(P_WORD) | curses.A_BOLD)
    y += 1
    for de, info in summary["review"]:
        if y >= height - 3:
            break
        draw_centered(stdscr, y, "  • %s (%s) — missed %d×" % (
            de, info["en"], info["count"]))
        y += 1
    if not summary["review"]:
        draw_centered(stdscr, y, "  (none — perfect!)", curses.A_DIM)
    draw_centered(stdscr, height - 2, "► ENTER: play again   Q: menu", curses.A_BOLD)
    stdscr.refresh()
