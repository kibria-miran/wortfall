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
- Playing: German words fall with English translations; Hallo and Tschüss also show Urdu. Type the German word; an exact match is accepted immediately on the final character, without Enter. Backspace edits.
- Speed: `+` increases and `-` decreases falling speed (0.25x steps; range 0.25x–3.00x).
- Infinite lives: press `I` to toggle.
- Exit: press `Esc` twice within 1.5 seconds. Press another key after the first Esc to cancel.
- Summary: Enter replay, M menu, Q quit

## Look and sound
- Dracula-theme UI (256-colour terminals recommended; falls back to 8 colours).
- Falling words read `[ German == English == Urdu ]`, e.g. `[ Hallo == Hello == ہیلو ]`.
  Every word gets random Dracula accent colours, and each language has its own style
  (German bold, English italic, Urdu regular weight).
- When you type a German word correctly its pronunciation is spoken (F2). Backends, best first:
  gTTS + mpv/ffplay/mpg123 (natural voice, cached in `~/.wortfall/audio`), then espeak-ng, then spd-say.
  Install: `sudo pacman -S espeak-ng` (offline) and optionally `pip install gtts` + `sudo pacman -S mpv`.
- Native sound effects (F3): correct chime, wrong buzz, miss descent, level-up
  fanfare, extra-life sparkle, streak riff, game-over dirge. Effects are
  synthesized with the Python stdlib into small WAVs (cached in `~/.wortfall/sfx`)
  and played through your system's native audio stack: `paplay` (PipeWire/PulseAudio,
  the Arch default), then `aplay` (ALSA), then `ffplay`; the terminal bell is the
  last-resort fallback. Enable with `sudo pacman -S pipewire-pulse` or `alsa-utils`.
- Visual polish: red-blinking urgent words near the bottom, a danger-zone band,
  green burst animation on solved words, missed words linger briefly showing the
  answer, boxed pause overlay, level progress and streak flames in the header.
- Keys: `F2` pronunciation, `F3` sound effects, `Tab` infinite lives, `+`/`-` speed,
  `U` (menu) Urdu display raw/shaped.
  If Urdu looks disconnected or reversed in your terminal, press `U` in the menu
  (needs `pip install arabic-reshaper python-bidi`).

## Learning features
- Falling prompts display German → English; `Hallo` and `Tschüss` additionally show Urdu. Type the German word; exact matches are detected after each keystroke, so Enter is not required.
- `+` / `-` adjust falling speed; `I`/`Tab` toggles infinite lives.
- `Esc` pauses; a later `Esc` resumes; a second `Esc` within 1.5 seconds saves and
  exits (any other key after the first `Esc` cancels the exit request).
- Articles required by default; optional mode accepts a noun without its article for half points; off mode omits articles.
- Umlaut alternatives are accepted: ä/ae, ö/oe, ü/ue, ß/ss.
- Plural mode only selects entries with a plural form.
- Category cycling, falling-word hints, weak-word weighted review, per-word statistics and high score.
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
