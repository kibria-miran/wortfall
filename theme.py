"""Neon Night colour theme, per-language text styles and Urdu display helpers."""
import curses

from textnorm import display_width as _display_width

# Neon Night palette -> nearest xterm-256 colour index (exact hex in comments).
PALETTE = {
    "bg": 234,       # #0b0e14 near-black
    "fg": 254,       # #e2e8f0 off-white
    "comment": 240,  # #4b5563 slate grey
    "cyan": 45,      # #00d7ff electric cyan
    "green": 48,     # #00ff87 neon green
    "orange": 208,   # #ff8700 hot amber
    "pink": 200,     # #ff5faf neon magenta
    "purple": 141,   # #af87ff violet
    "red": 203,      # #ff5f5f hot red
    "yellow": 220,   # #ffd700 amber gold
}
# 8-colour fallback for terminals without 256 colours.
FALLBACK = {"bg": curses.COLOR_BLACK, "fg": curses.COLOR_WHITE, "comment": curses.COLOR_BLUE,
            "cyan": curses.COLOR_CYAN, "green": curses.COLOR_GREEN, "orange": curses.COLOR_YELLOW,
            "pink": curses.COLOR_MAGENTA, "purple": curses.COLOR_MAGENTA, "red": curses.COLOR_RED,
            "yellow": curses.COLOR_YELLOW}
from config import ACCENTS, random_word_colors  # noqa: F401  (random word colours)
PAIRS = {}   # colour name -> curses attribute (foreground on Neon Night background)
BG_ATTR = 0

def init_theme(stdscr):
    """Create colour pairs and paint the whole screen with the Neon Night background."""
    global BG_ATTR
    PAIRS.clear()
    if not curses.has_colors(): return
    try:
        curses.start_color()
        table = PALETTE if curses.COLORS >= 256 else FALLBACK
        for n, name in enumerate(table, 1):
            curses.init_pair(n, table[name], table["bg"])
            PAIRS[name] = curses.color_pair(n)
        BG_ATTR = PAIRS["fg"]
        stdscr.bkgd(" ", BG_ATTR)
    except curses.error:
        PAIRS.clear()

def color(name): return PAIRS.get(name, 0)

# Per-language "font style". A terminal has one font, so styles are text attributes.
ITALIC = getattr(curses, "A_ITALIC", curses.A_UNDERLINE)
STYLE_DE = curses.A_BOLD            # German: bold
STYLE_EN = ITALIC                   # English: italic
STYLE_UR = curses.A_NORMAL          # Urdu: regular weight

def display_width(text):
    """Terminal cell width (implemented in textnorm so game logic can use it too)."""
    return _display_width(text)

_shaping_ok = None
def shaping_available():
    global _shaping_ok
    if _shaping_ok is None:
        try:
            import arabic_reshaper, bidi.algorithm  # noqa: F401
            _shaping_ok = True
        except Exception:
            _shaping_ok = False
    return _shaping_ok

def urdu_text(text, shaped=False):
    """Raw text works in terminals that shape Arabic script themselves; `shaped` joins and
    reverses letters for terminals that do not (needs: pip install arabic-reshaper python-bidi)."""
    if shaped and shaping_available():
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(text))
    return text
