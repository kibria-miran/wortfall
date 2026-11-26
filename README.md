# WORTFALL — German A1 Typing Game

A terminal-based German vocabulary game built with Python 3.10+ and standard-library `curses`.

## Run
```bash
python main.py
```
Windows requires `pip install windows-curses` (untested — developed on Arch Linux). Use a
terminal at least 80 columns × 24 rows. Progress autosaves every 30 s and on every exit
(including Ctrl+C) to `~/.wortfall/progress.json`.

## Classic mini variant (cannon mode)
A compact single-file take on the same idea lives alongside the main game. Words fall as
`German = English = Urdu` and a cannon fires at each word you finish; typing is truly
character-by-character (finished letters turn green), so no Enter and no auto-complete.

```bash
python3 wortfall.py                 # Roman Urdu glosses
python3 wortfall.py --urdu-script   # Urdu script (needs a terminal font that supports it)
```

- 72 core words in `words.py` (`(article, german, english, urdu_script, urdu_roman)`).
- Umlaut shortcut here differs from the main game: type `a/o/u` for `ä/ö/ü` and `ss` for `ß`.
- `TAB` resets the current word, `ESC` quits, `R` restarts on the game-over screen.

## How it teaches
- **Recall mode (default OFF):** words fall as `[ das Haus == house == گھر ]` so you can
  see the German. Press `R` in the menu to switch it ON for real practice —
  `[ _ == house == گھر ]`, meaning only, and you produce the German from memory.
- **Pronunciation at spawn:** every word is spoken (F2 to enable backends) the moment it
  appears, so ear + eye + hand are linked. Correct typing stays silent — no chime.
- **Weak-word review (default ON, `W` toggles):** unseen and often-missed words fall more
  often, using the progress this game tracks. OFF = pure random order.
- **Conjugation hints:** words with a `note` (e.g. *sein → ich bin; du bist; er ist*)
  show it in the hint bar late in the fall and under the word in learn mode.
- **Long words get more time:** fall speed scales +0.3 s per character, so
  *Krankenschwester* is not falling as fast as *ja*.
- **Misc:** plural prompts are marked `house (pl.)`; typing the full article (`dashaus`)
  scores 1.5× the bare noun (`haus`) in the default optional-article mode; gender show
  hints color-code der/die/das.

## Controls
- Menu: Enter start, C category, A article mode, P plural mode, **R recall mode**,
  **W weak-word review**, L learn mode, U Urdu shaping, F2/F3 audio, Q quit.
  Categories or settings with no words are refused with a message.
- Playing: type the German; the match fires on the final character, no Enter needed.
  **SPACE resets typing.** Mistyped letters that can no longer become any falling word
  are flagged immediately (red feedback) and count as a real mistake.
- Learn mode (`?` or `!`): skip/reveal the answer — it counts as a miss and is re-queued
  after 3 resolved words.
- Pause: `ESC` — **any key resumes**, `Q` saves and quits.
- Exit from menu/summary: `ESC` twice within 1.5 s (other keys cancel).
- Speed: `+` / `-` (0.25× steps, clamped 0.25×–3.00×). Tab toggles infinite lives.
- Summary: `1 s` input cooldown, then Enter replay, M menu, Q quit.

## Fair high score
TAB (infinite lives) or slowing the game below 1.0× marks the session as practice; the
high score is only recorded from clean sessions (learn-mode sessions too). The score is
saved whenever you quit, not only at game over.

## Look and sound
- Clean **Neon Night** theme (near-black + electric cyan/amber/magenta; 256-colour
  terminals recommended, falls back to 8 colours):
  one-line header `WORTFALL · SCORE · ♥♥♥ · LV · ×streak`, minimal hint and typing lines.
- Living background: twinkling stars, birds flying across the sky, and weather that
  slowly cycles clear → cloudy → rain → snow.
- Sound effects (F3) only for wrong buzz, miss, level-up, extra life, streak and
  game-over — synthesized with the Python stdlib into small WAVs (cached in
  `~/.wortfall/sfx`) and played natively: `paplay` (PipeWire/PulseAudio, the Arch
  default), then `aplay` (ALSA), then `ffplay`; the terminal bell is the last-resort
  fallback. Enable with `sudo pacman -S pipewire-pulse` or `alsa-utils`.
- Pronunciation (F2): gTTS + mpv/ffplay/mpg123 (natural voice, cached in
  `~/.wortfall/audio`), then espeak-ng, then spd-say.
  Install: `sudo pacman -S espeak-ng` (offline) and optionally `pip install gtts` + `sudo pacman -S mpv`.
- Visual polish: red-blinking urgent words near the bottom, green burst on solved
  words, missed words linger briefly showing the answer, boxed pause overlay.
- Urdu display shaped/raw with `U` (shaped needs `pip install arabic-reshaper python-bidi`).

## Vocabulary
- 480 A1 entries in `words.json`: nouns with articles + plurals, verbs (with
  conjugation notes), adjectives, numbers, question words, prepositions, connectors,
  phrases, seasons — including the tables from *Deutsch lernen — German Learning Guide*.
- No special keyboard needed: ä=ae, ö=oe, ü=ue, ß=ss (`strasse` = `Straße`), and
  punctuation is ignored (`wie gehts` = `Wie geht's?`).
- Translations lean on the guide; Urdu strings are best-effort and worth a native check.

## Tests
```bash
python3 selftest.py
```
Covers vocab validation, umlaut/punctuation normalization, recall defaults, article
bonus, prefix-collision guard, weighted vs random picking, speed clamping, recordable
high scores, learn-mode skip/requeue, empty categories, dead-prefix mistakes, SFX synthesis.

## Project structure
`main.py`, `game.py`, `word.py`, `renderer.py`, `input_handler.py`, `vocab.py`,
`progress.py`, `textnorm.py`, `theme.py`, `audio.py`, `sfx.py`, `config.py`,
`words.json`, `launch.sh`.
