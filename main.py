#!/usr/bin/env python3
"""WORTFALL — German A1 vocabulary typing game (stdlib curses only).

Run:           python3 main.py
Headless test: python3 main.py --test
"""

import curses
import json
import os
import sys
import time

import renderer
from config import CONFIG
from game import GameState
from input_handler import InputHandler
from vocab import categories, load_words

HIGHSCORE_PATH = os.path.expanduser("~/.wortfall_scores.json")


def load_high_score():
    try:
        with open(HIGHSCORE_PATH, encoding="utf-8") as f:
            return int(json.load(f).get("high_score", 0))
    except (OSError, ValueError, AttributeError):
        return 0


def save_high_score(score):
    try:
        with open(HIGHSCORE_PATH, "w", encoding="utf-8") as f:
            json.dump({"high_score": score}, f)
    except OSError:
        pass


def play_session(stdscr, entries, cfg):
    state = GameState(entries, cfg)
    handler = InputHandler(state)
    stdscr.nodelay(True)
    frame = 1.0 / cfg["fps"]

    last = time.perf_counter()
    while not state.game_over and not state.quit_to_menu:
        now = time.perf_counter()
        dt = now - last
        last = now

        while True:
            key = stdscr.getch()
            if key == -1:
                break
            handler.handle(key)

        layout = renderer.compute_layout(stdscr)
        state.update(dt, layout["play_height"], layout["width"])
        renderer.draw_game(stdscr, state, layout)
        stdscr.refresh()

        spare = frame - (time.perf_counter() - now)
        if spare > 0:
            time.sleep(spare)
    return state


def menu(stdscr, cfg, category, high_score):
    stdscr.nodelay(False)
    while True:
        renderer.draw_menu(stdscr, cfg["articles_required"], category, high_score)
        key = stdscr.getch()
        if key in (10, 13, curses.KEY_ENTER):
            return "start"
        if key in (ord("c"), ord("C")):
            return "category"
        if key in (ord("a"), ord("A")):
            cfg["articles_required"] = not cfg["articles_required"]
        elif key in (ord("q"), ord("Q"), 27):
            return "quit"


def select_category(stdscr, current):
    cats = categories()
    while True:
        renderer.draw_category_select(stdscr, cats, current, len(load_words()))
        key = stdscr.getch()
        if key in (10, 13, curses.KEY_ENTER, 27):
            return "all"
        if key in (ord("q"), ord("Q")):
            return current
        if ord("1") <= key <= ord("9"):
            idx = key - ord("1")
            if idx < len(cats):
                return cats[idx]


def game_over_screen(stdscr, state, high_score):
    summary = state.summary()
    new_high = state.score > high_score
    if new_high:
        save_high_score(state.score)
    stdscr.nodelay(False)
    curses.flushinp()
    while True:
        renderer.draw_game_over(stdscr, summary, max(high_score, state.score), new_high)
        key = stdscr.getch()
        if key in (10, 13, curses.KEY_ENTER):
            return "restart"
        if key in (ord("q"), ord("Q"), 27):
            return "menu"


def curses_main(stdscr):
    renderer.init_colors(stdscr)
    stdscr.keypad(True)
    try:
        curses.set_escdelay(25)
    except AttributeError:
        pass
    curses.curs_set(0)

    cfg = dict(CONFIG)
    category = "all"
    high_score = load_high_score()

    while True:
        action = menu(stdscr, cfg, category, high_score)
        if action == "quit":
            return
        if action == "category":
            category = select_category(stdscr, category)
            continue

        entries = load_words(category=category)
        if not entries:
            category = "all"
            entries = load_words()

        while True:
            state = play_session(stdscr, entries, cfg)
            if state.quit_to_menu:
                break
            action = game_over_screen(stdscr, state, high_score)
            high_score = max(high_score, state.score)
            if action != "restart":
                break


def selftest():
    """Headless simulation of the full game logic (no curses needed)."""
    import random
    import config
    from config import fall_speed, max_words, spawn_interval
    from word import FallingWord, normalize

    entries = load_words()
    assert len(entries) >= 150, "expected 150+ words, got %d" % len(entries)

    w = FallingWord(entries[0], 5, 0.0)
    assert not w.exploding
    assert w.article and w.gender

    # umlaut normalization
    assert normalize("käse") == normalize("kaese") == normalize("KÄSE")
    fw = FallingWord({"de": "der Käse", "en": "cheese", "category": "food"}, 0, 0.0)
    assert fw.matches("käse") and fw.matches("kaese") and fw.matches("KÄSE") \
        and not fw.matches("kaas")

    # article toggle
    config.CONFIG["articles_required"] = True
    assert fw.matches("das käse") is False
    assert fw.matches("der Käse") and fw.matches("der kaese")
    config.CONFIG["articles_required"] = False
    assert fw.matches("das käse") is False  # extra word breaks exact match

    # difficulty helpers
    assert abs(spawn_interval(1) - 3.0) < 1e-9
    assert abs(spawn_interval(13) - 1.2) < 1e-9
    assert abs(fall_speed(10) / fall_speed(1) - 2.0) < 0.02
    assert max_words(1) == 2 and max_words(3) == 3 and max_words(11) == 6

    # simulated session: 60s of play, decent player
    random.seed(7)
    state = GameState(entries, dict(CONFIG))
    play_height, width = 20, 80
    for _ in range(60 * 60):
        state.update(1 / 60, play_height, width)
        if state.game_over:
            break
        if random.random() < 0.10:
            actives = state.active_words()
            if actives:
                target = max(actives, key=lambda w: w.y)
                state.input_buffer = target.target_text()
                state.submit_input()

    assert state.correct_count > 10, "player should score: only %d" % state.correct_count
    assert state.correct_count % CONFIG["level_up_every"] == 0 or state.level > 1
    summary = state.summary()
    assert summary["score"] > 0
    assert all(info["count"] >= 1 for _, info in summary["review"])

    print("words.json entries : %d" % len(entries))
    print("categories         : %d" % len(categories()))
    print("sim correct        : %d   escapes: %d   mistakes: %d"
          % (state.correct_count, state.escaped_count, state.mistake_count))
    print("sim score          : %d   level: %d   best streak: x%d"
          % (state.score, state.level, state.best_streak))
    print("selftest OK")
    return 0


def run():
    try:
        curses.wrapper(curses_main)
    except curses.error as exc:
        sys.exit("curses error: %s (is your terminal big enough? min 80x24, "
                 "and TERM must be set)" % exc)


if __name__ == "__main__":
    if "--test" in sys.argv:
        selftest()
    else:
        run()
