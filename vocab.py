"""Vocabulary loading, validation, category filtering and the word picker."""
import json
import random
from collections import deque
from pathlib import Path

from config import CONFIG
from textnorm import normalize

ALLOWED_POS = {"noun","verb","adj","num","phrase","pron","prep","adv","q"}
REQUIRED = {"de","en","pos","pl","category"}

def validate_entry(row, index=0):
    if not isinstance(row, dict): return None, "row is not an object"
    missing = REQUIRED - row.keys()
    if missing: return None, "missing keys: " + ", ".join(sorted(missing))
    if not all(isinstance(row[k], str) and row[k].strip() for k in ("de","en","pos","category")):
        return None, "de/en/pos/category must be non-empty strings"
    if row["pos"] not in ALLOWED_POS: return None, "invalid part of speech"
    if row["pos"] == "noun" and not row["de"].startswith(("der ","die ","das ")):
        # Capitalized weekdays/months are proper nouns; they intentionally have no article in common use.
        if row["category"] not in {"weekdays","months"}:
            return None, "noun must include der/die/das"
    if row["pl"] is not None and not isinstance(row["pl"], str):
        return None, "plural must be string or null"
    return dict(row), None

def load_vocab(path=None):
    path = Path(path) if path else Path(__file__).with_name("words.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list): raise ValueError("words.json must contain a list")
    result, seen = [], set()
    for i, row in enumerate(data, 1):
        clean, error = validate_entry(row, i)
        if error:
            print(f"Warning: words.json row {i} skipped: {error}"); continue
        if clean["de"] in seen:
            print(f"Warning: duplicate German word skipped: {clean['de']}"); continue
        seen.add(clean["de"]); result.append(clean)
    if not result: raise ValueError("No valid vocabulary entries found")
    return result

def filter_by_category(words, categories=None):
    return list(words) if not categories else [w for w in words if w["category"] in categories]

def eligible_words(words, plural_mode=False):
    return [w for w in words if w.get("pl")] if plural_mode else list(words)

def count_words(words, categories=None, plural_mode=False):
    """How many words a session would get with these menu settings (2.15 guard)."""
    return len(eligible_words(filter_by_category(words, categories), plural_mode))

def word_key(word):
    """Typed-form key of an entry: normalized, spaces removed (2.1/2.2 guard)."""
    return normalize(word["de"]).replace(" ", "")

class Picker:
    """Chooses the next falling word.

    - Collision guard: never return a word whose typed key is equal to, a prefix
      of, or a superstring of a currently falling word's key (es/essen, a/an, sie/Sie).
    - Random order with optional weak-word weighting: unseen and often-missed
      words come back more often; perfectly-known words get no boost. Toggleable
      for pure random order.
    """
    def __init__(self, words, progress=None, recent_max=8, weighted=True):
        self.words = list(words)
        self.progress = progress or {}
        self.recent = deque(maxlen=recent_max)
        self.weighted = weighted

    def weight(self, word):
        stats = self.progress.get(word["de"], {})
        seen, missed = stats.get("seen", 0), stats.get("missed", 0)
        if not seen:
            return CONFIG["unseen_weight"]
        ratio = missed / max(1, seen)
        return 1.0 + CONFIG["missed_weight"] * min(ratio, 1.0)

    def pick(self, active_keys=()):
        active = set(active_keys)

        def collides(word):
            key = word_key(word)
            return any(k == key or k.startswith(key) or key.startswith(k) for k in active)

        # Fallback order keeps the collision guard strongest: a stuck pool relaxes
        # the recent-words rule first, exact-duplicate exclusion last.
        pool = [w for w in self.words
                if word_key(w) not in self.recent and not collides(w)]
        if not pool:
            pool = [w for w in self.words if not collides(w)]
        if not pool:
            pool = [w for w in self.words
                    if word_key(w) not in self.recent]
        if not pool:
            pool = list(self.words)
        if not pool: return None
        if self.weighted:
            word = random.choices(pool, weights=[self.weight(w) for w in pool], k=1)[0]
        else:
            word = random.choice(pool)
        self.recent.append(word_key(word))
        return word
