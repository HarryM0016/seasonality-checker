import re
import unicodedata
from functools import lru_cache

import inflect

_inflect_engine = inflect.engine()

_WORD_PATTERN = re.compile(r"[a-z0-9]+")


def normalise_text(text: str) -> str:
    """Normalise a phrase for lookup: "Coriander/Cilantro Leaves" -> "coriander cilantro leaf"."""
    return " ".join(tokenise(text))


def tokenise(text: str) -> list[str]:
    """split_words, then singularise each word."""
    return [singularise(word) for word in split_words(text)]


def split_words(text: str) -> list[str]:
    """Lowercase, strip accents, split on anything that isn't a letter/digit."""
    return _WORD_PATTERN.findall(remove_accents(text.lower()))


def remove_accents(text: str) -> str:
    normalised = unicodedata.normalize("NFD", text)
    return "".join(char for char in normalised if unicodedata.category(char) != "Mn")


@lru_cache(maxsize=4096)
def singularise(word: str) -> str:
    singular = _inflect_engine.singular_noun(word)
    return singular if singular else word
