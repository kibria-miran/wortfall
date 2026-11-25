"""FallingWord entity plus German text normalization (umlauts, articles)."""

import random

from config import CONFIG

NORMALIZE_MAP = str.maketrans({
    "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
    "Ä": "ae", "Ö": "oe", "Ü": "ue",
})

GENDER_LABEL = {
    "der": "masculine",
    "die": "feminine",
    "das": "neuter",
}


def normalize(s):
    """Lowercase, fold umlauts (ä->ae etc.), trim and collapse whitespace."""
    s = s.translate(NORMALIZE_MAP).lower().strip()
    return " ".join(s.split())


def common_prefix_len(a, b):
    n = 0
    for ca, cb in zip(a, b):
        if ca != cb:
            break
        n += 1
    return n


class FallingWord:
    def __init__(self, entry, x, spawn_time, speed_mult=1.0):
        self.de = entry["de"]
        self.en = entry["en"]
        self.category = entry.get("category", "")
        parts = self.de.split(" ", 1)
        if len(parts) == 2 and parts[0].lower() in GENDER_LABEL:
            self.article = parts[0]
            self.noun = parts[1]
        else:
            self.article = ""
            self.noun = self.de
        self.gender = GENDER_LABEL.get(self.article.lower(), "")

        self.x = x
        self.y = 0.0
        self.spawn_time = spawn_time
        self.speed = speed_mult * random.uniform(
            1 - CONFIG["speed_variance"], 1 + CONFIG["speed_variance"]
        )
        self.matched = False
        self.explode_start = None

    @property
    def exploding(self):
        return self.explode_start is not None

    def update(self, dt):
        if not self.exploding:
            self.y += self.speed * dt

    def target_text(self):
        """What the player must type (article included only if required)."""
        if CONFIG["articles_required"] and self.article:
            return self.de
        return self.noun

    def matches(self, input_text):
        return normalize(input_text) == normalize(self.target_text())

    def explosion_frame(self, now):
        frames = ["*", "*.*", "***", "."]
        if self.explode_start is None:
            return None
        step = int((now - self.explode_start) / (CONFIG["explosion_time"] / len(frames)))
        if step >= len(frames):
            return frames[-1]
        return frames[step]
