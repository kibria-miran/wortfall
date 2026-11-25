# WORTFALL

A terminal typing game for learning **German A1 vocabulary**. English words
fall from the top — type the German word and hit ENTER before they land.

Pure Python standard library (`curses`). **No pip dependencies.** Works on
Linux (including Arch), macOS, and WSL.

## Run (Arch Linux)

```bash
cd wortfall
python3 main.py
```

That's it — Python 3.10+ ships with `curses`. If it's somehow missing:
`sudo pacman -S python` (curses is included in the stdlib package).

Optional: `python3 main.py --test` runs a headless logic self-test.

## How to play

| Key | Action |
|---|---|
| letters / space | type the German word |
| `ae` `oe` `ue` `ss` | accepted instead of `ä ö ü ß` (and vice versa) |
| **Backspace** | fix a typo |
| **ENTER** | submit — matches against **any** falling word |
| **ESC** | pause (Q in pause quits to menu) |

- Correct: **+10 × level**, +5 speed bonus if answered within 2s of spawn.
- Streaks: 3+ in a row = ×1.5 points, 5+ = ×2. Every 5 in a row: **+1 life** (max 5).
- Wrong submit: −5 points, streak reset. Word hits bottom: **−1 life**.
- Level up every 10 correct words → words fall faster and spawn sooner.
- Match is case-insensitive; you can target any word, not just the lowest.

## Menu options

- **C** — play a single category (food, animals, verbs, numbers, months, …)
- **A** — toggle article mode: type `das haus` instead of just `haus`
- High score persists in `~/.wortfall_scores.json`

## Learning features

- Hint bar shows the **article + gender** for the lowest word
  (`der`=`blau`, `die`=`rot`, `das`=`grün` — classic German-learning colors).
- Wrong answers show the correct German word with its gender.
- Game-over summary lists the words you missed most, for review.
- Vocabulary: ~190 A1 words in `words.json` (edit to add your own:
  `{"de": "der Löffel", "en": "spoon", "category": "food"}`).

## Files

```
main.py           entry point, menus, game loop
game.py           GameState: scoring, lives, levels, matching
word.py           FallingWord + umlaut normalization
input_handler.py  keyboard handling
renderer.py       curses drawing
vocab.py          word loading + non-repeating pool
config.py         all tuning constants
words.json        vocabulary data
```

Works in any terminal ≥ 80×24.
