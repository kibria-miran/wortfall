#!/usr/bin/env python3
"""Merkhilfe - memorize German sentences with sound-alike words and silly stories.
Usage: python3 merkhilfe.py [learn|quiz]"""
import json, random, re, sys
from mnemonics import SENTENCES
from config import APP_DIR

try:
    import audio
    speak = audio.get_speaker().speak
except Exception:
    speak = lambda t: None

B, Y, G, R, D, X = "\033[1m", "\033[1;33m", "\033[32m", "\033[31m", "\033[2m", "\033[0m"
PROG = APP_DIR / "mnemonics.json"
MAP = {"ä": "a", "ö": "o", "ü": "u", "ß": "ss"}

def key(s): return re.sub(r"[^a-z0-9]", "", "".join(MAP.get(c, c) for c in s.lower()))
def hl(s): return re.sub(r"\*(.+?)\*", Y + r"\1" + X, s)
def clear(): print("\033[2J\033[H", end="")
def ask(p):
    try: return input(p).strip()
    except (EOFError, KeyboardInterrupt): print(); return "q"

def load():
    try: return set(json.load(open(PROG, encoding="utf-8")).get("known", []))
    except (OSError, ValueError): return set()
def save(known):
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        json.dump({"known": sorted(known)}, open(PROG, "w", encoding="utf-8"), ensure_ascii=False)
    except OSError: pass

def head(i, n, s):
    clear(); print(f"{D}[{i}/{n}]{X}\n\n  {B}{s[0]}{X}\n  = {s[1]}\n  = {s[2]}\n")

def learn():
    for i, s in enumerate(SENTENCES, 1):
        head(i, len(SENTENCES), s); speak(s[0])
        if ask(f"{D}ENTER = sound-alikes, q = quit {X}").lower() == "q": return
        for de, en, ur, sounds in s[3]:
            print(f"  {B}{de:<9}{X} = {en} = {ur}\n            {Y}~ {' / '.join(sounds)}{X}")
        if ask(f"\n{D}ENTER = story {X}").lower() == "q": return
        print("\n  " + hl(s[4]) + "\n")
        if ask(f"{D}ENTER = next, q = quit {X}").lower() == "q": return

def quiz():
    known = load()
    queue = [s for s in SENTENCES if s[0] not in known] or list(SENTENCES)
    random.shuffle(queue)
    while queue:
        s = queue.pop(0)
        clear(); print(f"{D}{len(queue) + 1} left, {len(known)} known{X}\n\n  = {s[1]}\n  = {s[2]}\n\n  " + hl(s[4]) + "\n")
        ans = ask("  type the German (? = sound-alikes, q = quit): ")
        if ans.lower() == "q": break
        if ans == "?":
            for de, en, ur, sounds in s[3]: print(f"   {en:<18}{Y}~ {' / '.join(sounds)}{X}")
            ans = ask("  type the German: ")
            if ans.lower() == "q": break
        if key(ans) == key(s[0]):
            known.add(s[0]); save(known); print(f"\n  {G}richtig!{X} {s[0]}"); speak(s[0])
        else:
            queue.append(s); print(f"\n  {R}not quite:{X} {B}{s[0]}{X}"); speak(s[0])
        ask(f"{D}ENTER {X}")
    save(known)
    print(f"\nKnown: {len(known)}/{len(SENTENCES)}")

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ask("[l]earn or [q]uiz? ").lower()[:1]
    if mode in ("l", "learn"): learn()
    elif mode in ("q", "quiz"): quiz()
