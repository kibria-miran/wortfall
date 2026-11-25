"""Vocabulary loading, category listing, and non-repeating word pool."""

import json
import os
import random

WORDS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "words.json")


def load_words(path=WORDS_PATH, category="all"):
    with open(path, encoding="utf-8") as f:
        entries = json.load(f)
    if category and category != "all":
        entries = [e for e in entries if e.get("category") == category]
    return entries


def categories(path=WORDS_PATH):
    with open(path, encoding="utf-8") as f:
        entries = json.load(f)
    return sorted({e["category"] for e in entries})


class WordPool:
    """Shuffled deck: serves each word once before reshuffling."""

    def __init__(self, entries):
        self.entries = list(entries)
        self._deck = []
        self.seen_de = set()

    def next(self):
        if not self._deck:
            self._deck = list(self.entries)
            random.shuffle(self._deck)
        entry = self._deck.pop()
        self.seen_de.add(entry["de"])
        return entry
