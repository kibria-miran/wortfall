#!/usr/bin/env python3
"""Headless self-test: game logic + audio synthesis, no curses needed.

Run: python3 selftest.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def main():
    import config
    config.PROGRESS_FILE = Path(tempfile.mkdtemp()) / "progress.json"

    import vocab
    import textnorm
    import game as game_mod
    from game import GameState, set_event_hook, set_spawn_hook
    from progress import Progress

    entries = vocab.load_vocab()
    assert len(entries) >= 450, f"expected 450+ vocab entries, got {len(entries)}"

    # normalization: umlauts, articles, punctuation, edit distance
    assert textnorm.normalize("Käse") == "kaese"
    assert textnorm.normalize("  DAS   Haus ") == "das haus"
    assert textnorm.normalize("Wie geht's?") == "wie gehts"
    assert textnorm.normalize("Ich heiße ...") == "ich heisse"
    assert textnorm.strip_article("die Straße") == "strasse"
    assert textnorm.article_of("der Zug") == "der"
    assert textnorm.article_of("essen") is None
    assert textnorm.edit_distance("haus", "maus") == 1
    assert textnorm.display_width("das Haus") == 8
    assert textnorm.display_width("درخت") == 4

    progress = Progress(config.PROGRESS_FILE)
    assert progress.data["version"] == 1
    state = GameState(entries, progress)
    assert state.field_height == 20
    assert state.recall_mode and state.weighted

    events = []
    set_event_hook(events.append)
    spoken = []
    set_spawn_hook(spoken.append)

    # --- play a simulated session (recall mode: type German from meaning)
    import random
    random.seed(3)
    state.spawn_timer = 0.0
    state.update(1 / 30, 80)
    assert state.words, "word should spawn"
    assert state.words[0].spawn_clock >= 0

    for _ in range(30 * 90):  # 90 simulated seconds
        state.update(1 / 30, 80)
        if state.game_over:
            break
        if random.random() < 0.12:
            falling = [w for w in state.words if w.state.value == "falling"]
            if falling:
                target = max(falling, key=lambda w: w.y)
                state.try_match(target.answer)

    assert state.correct_count > 5, f"should score, only {state.correct_count}"
    assert state.score > 0
    assert "solve" not in events, "solve chime should be silent on correct words"
    assert spoken, "spawn speech hook should fire"
    summary = state.summary()
    assert 0 <= summary["accuracy"] <= 100

    # --- SPACE resets the typed buffer
    from input_handler import handle_key
    state.input_buffer = "das h"
    handle_key(" ", state)
    assert state.input_buffer == "", "SPACE must clear the typing buffer"

    # --- multi-word answers match without spaces (SPACE is never part of the answer)
    haus = next(e for e in entries if textnorm.normalize(e["de"]) == "das haus")
    state3 = GameState(entries, progress, articles_mode="optional")
    state3._spawn_specific(haus, 80)
    assert state3.try_match("das haus"), "spaceless \"das haus\" input must match \"das Haus\""
    state3 = GameState(entries, progress, articles_mode="optional")
    state3._spawn_specific(haus, 80)
    assert state3.try_match("haus"), "article-free noun must be accepted"

    # --- article bonus: typed WITH article scores 1.5x the bare noun
    def score_for(typed):
        st = GameState(entries, progress, articles_mode="optional")
        st._spawn_specific(haus, 80)
        w = next(w for w in st.words if w.state.value == "falling")
        st.try_match(typed)
        return st.score, w
    s_with, _ = score_for("dashaus")
    s_without, _ = score_for("haus")
    assert s_with == round(s_without * config.CONFIG["article_bonus"]), \
        f"article bonus broken: {s_with} vs {s_without}"

    # --- 2.1/2.2: picker never returns a word whose key collides with an active key
    colliding_entries = [w for w in entries
                         if textnorm.normalize(w["de"]) in {"an", "ankommen", "anrufen"}]
    assert len(colliding_entries) >= 2
    active = [vocab.word_key({"de": "ankommen"})]
    picker = vocab.Picker(colliding_entries, {}, recent_max=1, weighted=False)
    for _ in range(300):
        picked = picker.pick(active)
        assert textnorm.normalize(picked["de"]) != "an", \
            "prefix word 'an' must not spawn next to 'ankommen'"

    # --- 1.3/1.5: weighted picker boosts weak words; toggle restores pure random
    biased = {"das Haus": {"seen": 100, "missed": 100}}
    counts = {"das Haus": 0}
    picker = vocab.Picker(entries, biased, recent_max=5, weighted=True)
    for _ in range(2000):
        if picker.pick()["de"] == "das Haus":
            counts["das Haus"] += 1
    mean = 2000 / len(entries)
    assert counts["das Haus"] > 1.3 * mean, \
        f"weak-word review not boosting: {counts['das Haus']} vs mean {mean:.1f}"
    picker.weighted = False
    counts = 0
    for _ in range(2000):
        if picker.pick()["de"] == "das Haus":
            counts += 1
    assert counts < 2.5 * mean, f"pure-random pick not uniform: {counts} vs mean {mean:.1f}"

    # --- 2.4: speed clamping must not drift word speeds
    st = GameState(entries, progress)
    st.spawn_timer = 0.0
    st.update(1 / 30, 80)
    w = next(w for w in st.words if w.state.value == "falling")
    base = w.speed
    for _ in range(10):
        st.change_speed(-0.25)
    assert st.speed_scale == 0.25
    assert abs(w.speed - base * 0.25) < 1e-6, "word speed drifted below scale"
    for _ in range(20):
        st.change_speed(0.25)
    assert st.speed_scale == 3.0
    assert abs(w.speed - base * 3.0) < 1e-6, "word speed drifted above scale"

    # --- 2.7: cheating with TAB or <1.0x speed blocks the high score
    assert st.recordable() is False, "3.0x is fair"
    st2 = GameState(entries, progress)
    assert st2.recordable() is True
    st2.toggle_infinite_lives()
    assert st2.recordable() is False

    # --- 2.3: learn mode skip reveals, counts as miss, re-queues after N turns
    learn = GameState(entries, progress, learn_mode=True)
    learn.spawn_timer = 0.0
    learn.update(1 / 30, 80)
    assert learn.words, "learn mode should spawn"
    assert not learn.learn_due, "nothing skipped yet"
    target = learn.words[0].entry
    handle_key("?", learn)
    assert learn.words[0].state.value == "missed"
    assert learn.learn_due, "skipped word must be re-queued"
    assert learn.learn_due[0][0] == learn.learn_turn + config.CONFIG["learn_requeue_turns"]
    assert learn.mistakes >= 1

    # --- 2.15: plural mode + small category is detected before the game starts
    assert vocab.count_words(entries, ["greetings"], plural_mode=True) == 0
    assert vocab.count_words(entries, ["food"], plural_mode=True) > 0
    assert vocab.count_words(entries, ["verbs"], plural_mode=False) > 0

    # --- 2.5: dead-prefix typing counts a real mistake
    st3 = GameState(entries, progress, recall_mode=False)
    st3.spawn_timer = 0.0
    st3.update(1 / 30, 80)
    st3.input_buffer = "zzzzz"
    mistakes_before = st3.mistakes
    handle_key("z", st3)
    assert st3.mistakes == mistakes_before + 1, "dead prefix must count a mistake"
    assert st3.input_buffer == "", "dead prefix must clear the buffer"

    # --- 1.5: plural prompts mark the plural gloss
    part = game_mod.make_parts("die Häuser", {"en": "house", "ur": "xx"}, plural=True)
    assert part[1] == "house (pl.)"

    # --- sound synthesis + native backend discovery
    import sfx as sfx_mod
    for name in ("wrong", "miss", "level_up", "life", "streak", "game_over"):
        path = sfx_mod.ensure_effect(name)
        assert path and path.exists() and path.stat().st_size > 400, f"{name}.wav broken"
    sfx_engine = sfx_mod.get_sfx()
    sfx_engine.play("wrong")    # non-blocking; bell fallback if no player installed
    sfx_engine.play("unknown")  # ignored silently

    print(f"vocab entries     : {len(entries)}")
    print(f"sim correct/score : {state.correct_count} / {state.score}  "
          f"level {state.level}  streak {state.streak}")
    print(f"sfx events fired  : {sorted(set(events))}")
    print(f"sfx backend       : {sfx_engine.backend} (wavs cached in {sfx_mod.SFX_DIR})")
    print(f"spawn speech      : {len(spoken)} words")
    print("selftest OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
