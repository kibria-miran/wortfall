"""WORTFALL — global tuning constants and derived difficulty helpers."""

CONFIG = {
    # gameplay toggles
    "articles_required": False,      # True = must type "das haus" (noun + article)
    "colors_enabled": True,
    "article_color_coding": True,    # der=blue, die=red, das=green in hint bar

    # lives
    "start_lives": 3,
    "max_lives": 5,
    "streak_life_every": 5,          # +1 life every N correct words in a row

    # falling speed (rows per second at level 1 = 1 row / 500ms)
    "fall_speed_base": 2.0,
    "speed_increase_per_level": 0.08,
    "speed_variance": 0.10,          # ±10% per-word variation

    # spawning
    "base_spawn_interval": 3.0,      # seconds
    "spawn_decrease_per_level": 0.15,
    "min_spawn_interval": 1.2,
    "base_max_words": 2,             # simultaneous words at level 1
    "max_words_on_screen": 6,

    # progression
    "level_up_every": 10,            # correct words needed per level

    # scoring
    "base_points": 10,               # × level
    "speed_bonus": 5,                # typed within speed_bonus_window of spawn
    "speed_bonus_window": 2.0,
    "wrong_penalty": 5,              # points lost on wrong submit
    "streak_mult_3": 1.5,            # streak >= 3
    "streak_mult_5": 2.0,            # streak >= 5

    # loop / effects
    "fps": 30,
    "explosion_time": 0.6,           # seconds the explosion animation stays
    "danger_rows": 2,                # bottom rows counted as danger zone
}


def spawn_interval(level: int) -> float:
    """Seconds between spawns at a given level."""
    return max(
        CONFIG["min_spawn_interval"],
        CONFIG["base_spawn_interval"] - CONFIG["spawn_decrease_per_level"] * (level - 1),
    )


def fall_speed(level: int) -> float:
    """Base falling speed in rows/second at a given level."""
    return CONFIG["fall_speed_base"] * (1 + CONFIG["speed_increase_per_level"]) ** (level - 1)


def max_words(level: int) -> int:
    """Maximum simultaneous non-exploding words on screen at a given level."""
    return min(
        CONFIG["max_words_on_screen"],
        CONFIG["base_max_words"] + (level - 1) // 2,
    )


def streak_multiplier(streak: int) -> float:
    if streak >= 5:
        return CONFIG["streak_mult_5"]
    if streak >= 3:
        return CONFIG["streak_mult_3"]
    return 1.0
