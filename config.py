"""Central, documented game configuration."""
from pathlib import Path

APP_DIR = Path.home() / ".wortfall"
PROGRESS_FILE = APP_DIR / "progress.json"
WORDS_FILE = Path(__file__).with_name("words.json")
CONFIG = {
    "articles_mode": "optional",     # SPACE resets typing, so 'optional' matches words with or without articles
    "plural_mode": False,
    "start_lives": 3, "max_lives": 5,
    "base_fall_speed": 0.8, "speed_growth": 1.08, "speed_cap": 3.0,
    "speed_jitter": 0.10, "base_spawn_interval": 3.0, "spawn_decay": 0.15,
    "min_spawn_interval": 1.2, "max_words_cap": 6, "recent_words_memory": 8,
    "level_up_every": 10, "streak_x1_5": 3, "streak_x2": 5,
    "wrong_penalty": 5, "speed_bonus_points": 5, "speed_bonus_fraction": 0.40,
    "fps": 30, "max_dt": 0.1, "input_buffer_max": 40,
    "min_terminal_width": 80, "min_terminal_height": 24,
    "explosion_time": 0.55,          # seconds solved/missed word animation stays
    "danger_rows": 2,                # bottom field rows tinted as the danger zone
    "learn_requeue_turns": 3,        # learn mode: resolve N words before a skipped one returns
    "autosave_seconds": 30,          # progress autosave interval during play
    "sfx_enabled": True,
    "sfx_volume": 0.45,              # 0.0–1.0 for synthesized effect wave files
    "en_ur_blink": 0.5,              # seconds per on/off phase of the blinking English/Urdu text
    "weather_cycle": 40.0,           # seconds per weather phase: clear → cloudy → rain → snow
    "recall_mode": False,            # True = hide the German; type it from the English/Urdu meaning
    "weak_word_review": True,        # weight the picker towards often-missed words
    "time_per_char": 0.3,            # extra fall seconds per character (long words get more time)
    "article_bonus": 1.5,            # optional-article mode: mult for typing "das haus" vs "haus"
    "unseen_weight": 1.5,            # picker weight for words never seen
    "missed_weight": 2.0,            # picker weight factor for missed/seen ratio
}

# Dracula accent colour names used for random word colours (see theme.py for the palette).
ACCENTS = ["cyan", "green", "orange", "pink", "purple", "red", "yellow"]

def random_word_colors(rng=None):
    """Three different accents: (German, English, Urdu)."""
    import random
    return tuple((rng or random).sample(ACCENTS, 3))
