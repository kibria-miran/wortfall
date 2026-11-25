# German A1 Typing Game - Design Document

## Game Name: **WORTFALL** (Word Fall)

## 1. CORE CONCEPT

A terminal-based typing game where German A1 vocabulary words fall from the
top of the screen. Each falling word shows the **English translation** (and
optionally the German article hint). The player must type the **correct
German word** before it reaches the bottom of the screen.

## 2. GAMEPLAY LOOP

1. A word spawns at top of screen showing English translation
2. Word falls downward at steady speed
3. Player types the German word
4. On correct match → word explodes, score += points
5. On wrong input → penalty (life or score)
6. If word reaches bottom → lose a life
7. Difficulty increases over time (faster fall, more words)
8. Game ends when lives = 0

## 3. SCREEN LAYOUT

```
┌─────────────────────────────────────────────────────────────┐
│  SCORE: 1250   LIVES: ♥♥♥   LEVEL: 3   STREAK: x4           │
├─────────────────────────────────────────────────────────────┤
│           [ house ]                                         │
│                          [ water ]                          │
│      [ apple ]                                              │
│                    [ book ]                                 │
├─────────────────────────────────────────────────────────────┤
│  HINT: "house" → das ___ (article: neuter)                  │
│  TYPE: das ha_                                              │
└─────────────────────────────────────────────────────────────┘
```

- Header bar: fixed top row with score/lives/level/streak
- Play field: dynamic height (terminal height - 4)
- Hint + input line: fixed bottom
- Falling words shown as `[ english ]`
- Active target word (closest to bottom) is highlighted bold

## 4. GAME MECHANICS

### 4.1 Word Spawning
- Spawn interval: starts 3.0s, −0.15s per level (min 1.2s)
- Max simultaneous words: 2, +1 per 2 levels (max 6)
- Random X column (avoid overlap near the top rows)

### 4.2 Falling Speed
- Base speed: 1 row per 500ms (2 rows/s)
- +8% per level
- Per-word variance ±10%

### 4.3 Scoring
- Correct word: **+10 × level**
- Speed bonus: within first 2s of spawn: **+5**
- Streak: 3+ consecutive = ×1.5, 5+ = ×2
- Wrong letter typed: no penalty (only on submit)
- Wrong word submitted (Enter): −5 points, streak reset
- Word reaches bottom: **−1 life**, streak reset

### 4.4 Lives
- Start: 3, max 5
- +1 life every 5 correct words in a row

### 4.5 Levels
- Level up every 10 correct words; message: "LEVEL UP! Speed increased"

### 4.6 Matching Logic
- Case-insensitive
- Articles: config toggle `articles_required`
  - off → type just noun: `haus`
  - on → type with article: `das haus`
- Umlauts: `ä`↔`ae`, `ö`↔`oe`, `ü`↔`ue`, `ß`↔`ss`
- Match is checked against **all active falling words** — any word can be targeted

## 5. VOCABULARY DATA

Stored in `words.json`, ~190 A1 entries:
`{"de": "das Haus", "en": "house", "category": "home"}`
Categories: home, food, animals, people, places, nature, objects, colors,
verbs, numbers, time, weekdays, months, family, body, clothes, adjectives.

## 6. TECH STACK

| Component | Choice |
|---|---|
| Language | Python 3.10+ |
| TUI | `curses` (stdlib, no deps) |
| Input | `curses.getch()` non-blocking |
| Data | `words.json` |

## 7. FILE STRUCTURE

```
wortfall/
├── main.py              # Entry point, game loop, menus
├── game.py              # Game state, logic
├── word.py              # FallingWord class, normalization
├── renderer.py          # curses drawing
├── input_handler.py     # Keyboard input, buffer
├── vocab.py             # Word loading, pool
├── config.py            # Constants
├── words.json           # Vocabulary data
├── DESIGN.md            # This document
└── README.md            # Instructions
```

## 8. KEY DESIGN POINTS

- 30 FPS loop, `nodelay(True)` polling input each frame
- Explosion animation frames: `*`, `*.*`, `***`, `.`
- Danger zone: bottom 2 rows of play field; words there turn red and blink
- `KEY_RESIZE` handled gracefully; layout recomputed every frame
- High score persisted to `~/.wortfall_scores.json`
- Umlaut input: `ae/oe/ue/ss` typed as ASCII work everywhere; raw UTF-8 bytes
  (C3 xx) are also mapped

## 9. COLORS

| Element | Color |
|---|---|
| Header | black on cyan |
| Falling words | yellow on black |
| Target word (lowest) | bold yellow |
| Correct flash / explosion | green |
| Wrong flash / danger | red |
| Input buffer | white on blue |
| Article hint | der=cyan, die=magenta, das=green |

## 10. GAME STATES

`MENU → PLAYING → PAUSED → PLAYING → GAME_OVER → MENU`

- MENU: title, ENTER start, C category, A article toggle, Q quit, high score
- CATEGORY: pick one category or all words
- PAUSED: overlay, timers frozen
- GAME_OVER: session summary (score, level, correct, mistakes, unique words,
  best streak, words needing review) → ENTER restart / Q menu

## 11. DIFFICULTY TABLE

| Level | Spawn (s) | Speed | Max words | Pts/word |
|-------|-----------|-------|-----------|----------|
| 1 | 3.0 | 1.0× | 2 | 10 |
| 2 | 2.85 | 1.08× | 2 | 20 |
| 3 | 2.70 | 1.17× | 3 | 30 |
| 5 | 2.40 | 1.36× | 3 | 50 |
| 10 | 1.65 | 2.0× | 5 | 100 |
| 11+ | min 1.2 | +8%/lvl | max 6 | ×10 |

## 12. TESTING CHECKLIST

- [x] Words spawn at correct interval
- [x] Words fall smoothly (float y, int row)
- [x] Umlaut matching (`kaese` = `käse`)
- [x] Article toggle works both ways
- [x] Lives decrement on missed word
- [x] Level up at correct count
- [x] Score multiplies with streak (×1.5 at 3+, ×2 at 5+)
- [x] Game over at 0 lives
- [x] Restart from menu
- [x] `KEY_RESIZE` handled
- [x] Works in 80×24
- Headless: `python3 main.py --test`

## 13. FUTURE (v2)

Sound effects, spaced repetition, learn mode, combo animations, boss words,
CSV export for Anki.
