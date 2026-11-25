"""Vocabulary loading, validation, category filtering and spaced-repetition picker."""
import json, random
from collections import deque
from pathlib import Path
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

class Picker:
    def __init__(self, words, progress=None, recent_max=8):
        self.words = list(words); self.progress = progress or {}
        self.recent = deque(maxlen=recent_max)
    def weight(self, word):
        stats = self.progress.get(word["de"], {})
        seen, missed = stats.get("seen",0), stats.get("missed",0)
        if not seen: return 2.0
        ratio = missed / max(1, seen)
        return 1.0 + 3.0 * ratio
    def pick(self, active_glosses=()):
        active = set(active_glosses)
        pool = [w for w in self.words if w["de"] not in self.recent and w["en"] not in active]
        if not pool: pool = [w for w in self.words if w["en"] not in active]
        if not pool: return None
        word = random.choices(pool, weights=[self.weight(w) for w in pool], k=1)[0]
        self.recent.append(word["de"])
        return word
