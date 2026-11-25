# WORTFALL — German A1 Typing Game

A terminal-based German vocabulary game built with Python 3.10+ and standard-library `curses`.

## Run
```bash
python main.py
```
Windows requires:
```powershell
py -m pip install windows-curses
py main.py
```
Use a terminal at least 80 columns × 24 rows. Progress is saved to `~/.wortfall/progress.json`.

## Controls
- Menu: Enter start, C cycle category, A article mode, P plural mode, L learn mode, Q quit
- Playing: words fall as `[ German == English == Urdu ]` — the English and Urdu blink
  on/off like a switching light while the German word stays constant. Type the German
  word; an exact match is accepted immediately on the final character, without Enter.
  Backspace edits.
- **SPACE resets typing** — clears the whole buffer if you want to restart a word.
  Multi-word answers never need a space: type `dashaus` or `haus` for `das Haus`.
- Speed: `+` increases and `-` decreases falling speed (0.25x steps).
- Infinite lives: press `Tab` to toggle.
- Exit: press `Esc` twice within 1.5 seconds. Press another key after the first Esc to cancel.
- Summary: Enter replay, M menu, Q quit

## Look and sound
- Clean Dracula-theme UI (256-colour terminals recommended; falls back to 8 colours):
  one-line header `WORTFALL · SCORE · ♥♥♥ · LV · ×streak`, minimal hint and typing lines.
- Living background: twinkling stars, birds flying across the sky, and weather that
  slowly cycles clear → cloudy → rain → snow.
- No chime on correct words (quiet on purpose). The German pronunciation is still
  spoken (F2). Backends, best first: gTTS + mpv/ffplay/mpg123 (natural voice, cached
  in `~/.wortfall/audio`), then espeak-ng, then spd-say.
  Install: `sudo pacman -S espeak-ng` (offline) and optionally `pip install gtts` + `sudo pacman -S mpv`.
- Sound effects (F3) only for the interesting moments: wrong buzz, miss descent,
  level-up fanfare, extra-life sparkle, streak riff, game-over dirge. Effects are
  synthesized with the Python stdlib into small WAVs (cached in `~/.wortfall/sfx`)
  and played natively: `paplay` (PipeWire/PulseAudio, the Arch default), then `aplay`
  (ALSA), then `ffplay`; the terminal bell is the last-resort fallback. Enable with
  `sudo pacman -S pipewire-pulse` or `alsa-utils`.
- Visual polish: red-blinking urgent words near the bottom, green burst on solved
  words, missed words linger briefly showing the answer, boxed pause overlay.
- Keys: `F2` pronunciation, `F3` sound effects, `Tab` infinite lives, `+`/`-` speed,
  `U` (menu) Urdu display raw/shaped.
  If Urdu looks disconnected or reversed in your terminal, press `U` in the menu
  (needs `pip install arabic-reshaper python-bidi`).

## Learning features
- 480 A1 words in `words.json` (nouns with articles + plurals, verbs, adjectives,
  numbers, question words, prepositions, phrases, seasons, connectors), including the
  vocabulary tables from *Deutsch lernen — German Learning Guide*. Spacebar-free
  typing for umlauts & ß: ä=ae, ö=oe, ü=ue, ß=ss (type `strasse` for `Straße`).
- Articles: optional mode (default) accepts `haus` or `dashaus` for `das Haus`, both at
  full points; required mode teaches the article; off mode ignores articles entirely.
- Umlaut alternatives are accepted: ä/ae, ö/oe, ü/ue, ß/ss.
- Words fall in a purely random order (recent words and words already on screen are
  skipped, but weak words are NOT boosted).
- Plural mode only selects entries with a plural form.
- Category cycling, falling-word hints, per-word statistics and high score.
- Learn mode removes the timer/lives and re-queues missed words after three turns.

## Tests
Headless check without a terminal (game logic + audio synthesis):
```bash
python3 selftest.py
```

## Project structure
`main.py`, `game.py`, `word.py`, `renderer.py`, `input_handler.py`, `vocab.py`,
`progress.py`, `textnorm.py`, `theme.py`, `audio.py`, `sfx.py`, `config.py`,
`words.json`, `launch.sh`.

## Double-click launch on Linux
Extract the ZIP, open the `wortfall` folder, and double-click `Wortfall.desktop`.
If your desktop environment asks, choose **Trust and Launch** or **Allow Launching**.
You can also run `./launch.sh` from a terminal.
