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
    from game import GameState, set_event_hook
    from progress import Progress

    entries = vocab.load_vocab()
    assert len(entries) >= 300, f"expected 300+ vocab entries, got {len(entries)}"

    # normalization: umlauts, articles, edit distance
    assert textnorm.normalize("Käse") == "kaese"
    assert textnorm.normalize("  DAS   Haus ") == "das haus"
    assert textnorm.strip_article("die Straße") == "strasse"
    assert textnorm.article_of("der Zug") == "der"
    assert textnorm.article_of("essen") is None
    assert textnorm.edit_distance("haus", "haus") == 0
    assert textnorm.edit_distance("haus", "maus") == 1

    progress = Progress(config.PROGRESS_FILE)
    state = GameState(entries, progress)
    assert state.field_height == 20

    events = []
    set_event_hook(events.append)
    spoken = []
    game_mod.set_solve_hook(spoken.append)

    # --- play a simulated session
    import random
    random.seed(3)
    state.spawn_timer = 0.0
    state.update(1 / 30, 80)
    assert state.words, "word should spawn"

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
    assert "solve" in events, "solve sfx event missing"
    assert spoken, "TTS hook should fire on correct answers"
    summary = state.summary()
    assert 0 <= summary["accuracy"] <= 100

    # --- article teaching prompt (required mode, article omitted)
    state2 = GameState(entries, progress, articles_mode="required")
    state2.spawn_timer = 0.0
    state2.update(1 / 30, 80)
    noun = next((w for w in state2.words if w.entry["pos"] == "noun"), None)
    if noun:
        state2.input_buffer = textnorm.strip_article(noun.answer)
        state2.submit()
        assert state2.input_buffer == "", "buffer should clear after teaching prompt"
        assert "Need the article" in state2.feedback

    # --- wrong word penalty + event
    state2.input_buffer = "xxxxxx"
    state2.submit()
    assert state2.mistakes == 1 and "wrong" in events

    # --- sound synthesis + native backend discovery
    import sfx as sfx_mod
    for name in ("solve", "wrong", "miss", "level_up", "life", "streak", "game_over"):
        path = sfx_mod.ensure_effect(name)
        assert path and path.exists() and path.stat().st_size > 400, f"{name}.wav broken"
    sfx_engine = sfx_mod.get_sfx()
    sfx_engine.play("solve")    # non-blocking; bell fallback if no player installed
    sfx_engine.play("unknown")  # ignored silently

    print(f"vocab entries     : {len(entries)}")
    print(f"sim correct/score : {state.correct_count} / {state.score}  "
          f"level {state.level}  streak {state.streak}")
    print(f"sfx events fired  : {sorted(set(events))}")
    print(f"sfx backend       : {sfx_engine.backend} (wavs cached in {sfx_mod.SFX_DIR})")
    print(f"tts spoken        : {len(spoken)} words")
    print("selftest OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
