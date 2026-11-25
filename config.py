"""Central, documented game configuration."""
from pathlib import Path

APP_DIR = Path.home() / ".wortfall"
PROGRESS_FILE = APP_DIR / "progress.json"
WORDS_FILE = Path(__file__).with_name("words.json")
CONFIG = {
    "articles_mode": "required", "plural_mode": False,
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
    "sfx_enabled": True,
    "sfx_volume": 0.45,              # 0.0–1.0 for synthesized effect wave files
}

# Dracula accent colour names used for random word colours (see theme.py for the palette).
ACCENTS = ["cyan", "green", "orange", "pink", "purple", "red", "yellow"]

def random_word_colors(rng=None):
    """Three different accents: (German, English, Urdu)."""
    import random
    return tuple((rng or random).sample(ACCENTS, 3))
