"""Game state and rules: spawning, falling, matching, scoring, lives, levels."""

import random
import time

from config import (
    CONFIG,
    fall_speed,
    max_words,
    spawn_interval,
    streak_multiplier,
)
from vocab import WordPool
from word import FallingWord, common_prefix_len, normalize


class GameState:
    def __init__(self, entries, cfg=None):
        self.cfg = cfg or CONFIG
        self.pool = WordPool(entries)

        self.score = 0
        self.lives = self.cfg["start_lives"]
        self.level = 1
        self.streak = 0
        self.best_streak = 0

        self.words = []
        self.input_buffer = ""
        self.spawn_timer = 0.5
        self.elapsed = 0.0

        self.correct_count = 0
        self.mistake_count = 0
        self.escaped_count = 0
        self.review = {}

        self.paused = False
        self.game_over = False
        self.quit_to_menu = False
        self.message = ""
        self.message_until = 0.0

    # ------------------------------------------------------------- helpers

    def active_words(self):
        return [w for w in self.words if not w.exploding]

    def target_word(self):
        """Lowest active falling word (the highlighted one)."""
        if not self.words:
            return None
        return max(self.active_words(), key=lambda w: w.y, default=None)

    def flash(self, text, seconds=1.5):
        self.message = text
        self.message_until = time.time() + seconds

    def add_review(self, word):
        info = self.review.setdefault(word.de, {"en": word.en, "count": 0})
        info["count"] += 1

    # -------------------------------------------------------------- update

    def update(self, dt, play_height, play_width):
        if self.paused or self.game_over:
            return

        self.elapsed += dt
        self.spawn_timer -= dt
        if self.spawn_timer <= 0 and len(self.active_words()) < max_words(self.level):
            self.spawn_word(play_width)
            self.spawn_timer = spawn_interval(self.level)

        speed = fall_speed(self.level)
        for word in self.words:
            word.update(dt * speed)

        for word in self.active_words():
            if word.y >= play_height:
                self.escape_word(word)

        now = time.time()
        self.words = [
            w for w in self.words
            if not w.exploding or (now - w.explode_start) < self.cfg["explosion_time"]
        ]

    def spawn_word(self, play_width):
        entry = self.pool.next()
        label = "[ %s ]" % entry["en"]
        max_x = max(1, play_width - len(label) - 2)
        x = 1
        for _ in range(12):
            candidate = random.randint(1, max_x)
            if not self._overlaps_at_top(candidate, len(label)):
                x = candidate
                break
        self.words.append(FallingWord(entry, x, time.time()))

    def _overlaps_at_top(self, x, length):
        for w in self.active_words():
            if w.y > 3:
                continue
            w_len = len(w.en) + 4
            if not (x + length < w.x or w.x + w_len < x):
                return True
        return False

    # ------------------------------------------------------------- results

    def escape_word(self, word):
        word.matched = True
        word.explode_start = time.time()
        self.add_review(word)
        self.escaped_count += 1
        self.streak = 0
        self.lives -= 1
        self.flash(
            '✗ "%s" (%s) escaped!  -1 life' % (word.de, word.en), 2.0
        )
        if self.lives <= 0:
            self.lives = 0
            self.game_over = True

    def submit_input(self):
        text = self.input_buffer.strip()
        self.input_buffer = ""
        if not text:
            return

        target = None
        for word in sorted(self.active_words(), key=lambda w: w.y, reverse=True):
            if word.matches(text):
                target = word
                break

        if target is not None:
            self.handle_correct(target)
        else:
            self.handle_wrong(text)

    def handle_correct(self, word):
        word.matched = True
        word.explode_start = time.time()

        self.streak += 1
        self.best_streak = max(self.best_streak, self.streak)
        self.correct_count += 1

        points = self.cfg["base_points"] * self.level
        mult = streak_multiplier(self.streak)
        if time.time() - word.spawn_time < self.cfg["speed_bonus_window"]:
            points += self.cfg["speed_bonus"]
        self.score += int(round(points * mult))

        if self.streak > 0 and self.streak % self.cfg["streak_life_every"] == 0 \
                and self.lives < self.cfg["max_lives"]:
            self.lives += 1
            self.flash("♥ EXTRA LIFE! (%s in a row)" % self.streak, 2.0)
        elif mult > 1.0:
            self.flash("✔ %s  + %s  (x%s streak)" % (word.de, points, mult), 1.0)
        else:
            self.flash("✔ %s  + %s" % (word.de, points), 1.0)

        if self.correct_count % self.cfg["level_up_every"] == 0:
            self.level += 1
            self.flash("★ LEVEL UP! Speed increased (level %s)" % self.level, 2.0)

    def handle_wrong(self, text):
        self.mistake_count += 1
        self.streak = 0
        self.score = max(0, self.score - self.cfg["wrong_penalty"])

        best = None
        best_len = -1
        norm_input = normalize(text)
        for word in self.active_words():
            n = common_prefix_len(norm_input, normalize(word.target_text()))
            if n > best_len:
                best, best_len = word, n

        if best is not None and best_len >= 2:
            self.add_review(best)
            gender = " (%s)" % best.gender if best.gender else ""
            self.flash('✗ "%s" → correct was "%s"%s' % (text, best.de, gender), 2.5)
        else:
            self.flash('✗ "%s" — no match!  -%s' % (text, self.cfg["wrong_penalty"]), 2.0)

    # ------------------------------------------------------------ summary

    def summary(self):
        weakest = sorted(self.review.items(), key=lambda kv: kv[1]["count"], reverse=True)
        return {
            "score": self.score,
            "level": self.level,
            "correct": self.correct_count,
            "mistakes": self.mistake_count,
            "escaped": self.escaped_count,
            "best_streak": self.best_streak,
            "unique_words": len(self.pool.seen_de),
            "review": weakest[:6],
        }
