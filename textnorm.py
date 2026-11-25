"""Unicode-friendly normalization, article handling, width and edit distance."""
import re
import unicodedata

ARTICLES = ("der", "die", "das")
MAP = {"ä":"ae", "ö":"oe", "ü":"ue", "ß":"ss"}
# punctuation/quotes/dots are never part of a typed answer ("Wie geht's?" == "wie gehts")
PUNCT = re.compile(r"[^\w\s]", re.UNICODE)

def normalize(value):
    if value is None:
        return ""
    value = " ".join(str(value).lower().strip().split())
    for src, dst in MAP.items():
        value = value.replace(src, dst)
    value = PUNCT.sub("", value)
    return " ".join(value.split())

def strip_article(value):
    value = normalize(value)
    for article in ARTICLES:
        if value.startswith(article + " "):
            return value[len(article) + 1:]
    return value

def article_of(value):
    first = str(value).strip().split(" ", 1)[0].lower()
    return first if first in ARTICLES else None

def edit_distance(a, b):
    a, b = normalize(a), normalize(b)
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(current[-1] + 1, previous[j] + 1,
                               previous[j-1] + (ca != cb)))
        previous = current
    return previous[-1]

def edit_distance_one(a, b):
    return normalize(a) != normalize(b) and edit_distance(a, b) == 1

def display_width(text):
    """Terminal cell width (combining marks take no cell)."""
    return sum(0 if unicodedata.combining(ch) or unicodedata.category(ch) == "Mn" else
               2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in str(text))
