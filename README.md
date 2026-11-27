# WORTFALL

Terminal typing game to learn German, with English and Urdu support
(`German = English = Urdu`). Pure Python 3 standard library — no pip dependencies.

## Run

```bash
python3 wortfall.py                 # main game (navigable menu)
python3 wortfall.py --urdu-script   # Urdu script glosses (default: Roman Urdu)
```

Use a terminal at least 80×24. A `.desktop` launcher is included.

## The loop: Merkhilfe + Sentences

1. **Merkhilfe trainer** — from the menu (or `python3 merkhilfe.py [learn|quiz]`):
   20 core A1 sentences, each broken down word by word into sound-alike rhymes you
   already know (English / Roman Urdu), then a silly story stringing the rhymes
   together:

   ```
   Ich trinke gern morgens einen Kaffee
   Ich   = I        = main      ~ itchy / ikh
   trinke = drink   = peeta hoon ~ twinkle / tri-nike
   gern  = gladly   = khushi se ~ germ
   ...
   *ITCHY* me (I) drinks *TWINKLE-NIKE* juice (drink); a *GERM* (like to) with
   *MORE GUNS* (morning) hands me *EYE-NEN* (a) *CALF-AY* (coffee).
   ```

   **learn** walks through sentences (ENTER next, `b` back, `q` quit);
   **quiz** shows the meaning + story and makes you type the German
   (`?` = sound-alike peek); known sentences are tracked in
   `~/.wortfall/mnemonics.json`.

2. **Sentences mode** — menu → *Sentences* (or press `s`): sentences fall and you
   type them character by character, in sequence-number order, no Enter. The pool
   contains the 20 Merkhilfe sentences plus 37 simple beginner phrases.

3. **In-game hooks** — while playing Sentences:
   - `?` opens the Merkhilfe card for the current sentence (sound-alikes + story),
     pausing the game until any key.
   - After you shoot a sentence down, a reminder line with its sound-alikes
     (`trinke ~ twinkle · morgens ~ more guns ...`) stays on screen for 6 s.

## Playing

- Type the **numbered** word 1, 2, 3 ... (lowest word first). No Enter needed —
  the cannon fires when the word is complete; typed letters light up green.
- Umlauts: type `a/o/u` for `ä/ö/ü`, `ss` for `ß` (spaces/punctuation ignored).
- `TAB` resets the current word, `ESC` back to the menu (game auto-saves,
  autosaves every 30 s, resumes via *Continue*).
- Menu: ↑↓ select, ←→ change values — category, start speed, Urdu script
  script/roman, sound on/off, Merkhilfe learn/quiz.
- `+`/`-` adjust speed in game, `F2`/`/` toggles sound.

## Vocabulary

`words.json` holds ~1,480 A1+ words in categories (nouns, verbs, food, family, ...);
`words.py` is the 72-word starter list used as fallback. Nouns carry their
der/die/das article.

## Files

| file | role |
|---|---|
| `wortfall.py` | main game (menu, falling words, cannon, sentences, save) |
| `merkhilfe.py` | memory trainer (learn / quiz), standalone or from the menu |
| `mnemonics.py` | the 20 sentences with per-word sound-alikes and stories |
| `sentences.py` | 37 simple practice sentences |
| `words.json` / `words.py` | vocabulary |
| `audio.py` / `config.py` | native sound playback and settings |
| `wortfall.desktop` | desktop launcher |
