"""Find fresh produce in raw recipe ingredient lines.

How a line is processed:
  1. Split into chunks on , ( ) / ; [ ]  - these separate list items and notes,
     so "lemon, salt" never treats "salt" as describing the lemon.
  2. Tokenise each chunk (lowercase, no accents, singular words).
  3. Greedy longest match against the alias table: try 3-word phrases, then 2, then 1,
     so "sweet potato" wins over "potato" and "green onion" over "onion".
  4. Exclude matches that describe a processed product rather than fresh produce:
       - a "before" word between the previous match and this one: "frozen peas", "desiccated coconut"
       - an "after" word between this match and the next one: "onion powder", "coconut or plain oil"
"""

from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable

from seasonality_checker.db import get_connection
from seasonality_checker.recipes.text_normaliser import normalise_text, tokenise

MAX_PHRASE_WORDS = 3

CHUNK_SEPARATORS = ",()/;[]"

# Words that, when they come before a produce word, mean it isn't fresh.
EXCLUDE_BEFORE = {
    "dried",
    "dehydrated",
    "desiccated",
    "frozen",
    "tinned",
    "canned",
    "powdered",
    "ground",
    "pickled",
    "candied",
    "crystallised",
    "crystallized",
    "preserved",
    "sundried",
}

# Words that, when they come after a produce word, mean it isn't fresh.
EXCLUDE_AFTER = {
    "powder",
    "paste",
    "puree",
    "stock",
    "broth",
    "sauce",
    "flakes",
    "granules",
    "oil",
    "cream",
    "milk",
    "water",
    "molasses",
    "jam",
    "jelly",
    "marmalade",
    "essence",
    "extract",
    "syrup",
    "cordial",
    "vinegar",
    "salt",
    "seasoning",
    "hoisin",
    "coulis",
    "curd",
}


@dataclass(frozen=True)
class ProduceMatch:
    produce: str  # canonical name, e.g. "coriander"
    matched_text: str  # normalised phrase that matched, e.g. "cilantro"
    excluded_by: str | None = None  # the word that disqualified it, e.g. "powder"

    @property
    def is_fresh(self) -> bool:
        return self.excluded_by is None


class ProduceMatcher:
    def __init__(self, aliases: Iterable[tuple[str, str]]):
        """aliases is (alias, canonical produce name) pairs, including each name mapped to itself."""
        self._lookup = build_lookup(aliases)
        self._exclude_before = {normalise_text(word) for word in EXCLUDE_BEFORE}
        self._exclude_after = {normalise_text(word) for word in EXCLUDE_AFTER}

    def match_line(self, line: str) -> list[ProduceMatch]:
        """Every produce mention in the line, including excluded ones."""
        matches = []
        for chunk in split_chunks(line):
            matches.extend(self._match_chunk(tokenise(chunk)))
        return matches

    def canonical_for(self, phrase: str) -> str | None:
        """The produce this phrase maps to if it is exactly an alias, e.g. "cilantro" -> "coriander"."""
        return self._lookup.get(normalise_text(phrase))

    def produce_in_line(self, line: str) -> set[str]:
        """Canonical names of the fresh produce in the line."""
        return {match.produce for match in self.match_line(line) if match.is_fresh}

    def _match_chunk(self, tokens: list[str]) -> list[ProduceMatch]:
        spans = self._find_spans(tokens)

        matches = []
        for i, (start, end, produce) in enumerate(spans):
            previous_end = spans[i - 1][1] if i > 0 else 0
            next_start = spans[i + 1][0] if i + 1 < len(spans) else len(tokens)

            excluded_by = first_in(
                tokens[previous_end:start], self._exclude_before
            ) or first_in(tokens[end:next_start], self._exclude_after)
            matches.append(
                ProduceMatch(produce, " ".join(tokens[start:end]), excluded_by)
            )
        return matches

    def _find_spans(self, tokens: list[str]) -> list[tuple[int, int, str]]:
        """Greedy, non-overlapping longest matches as (start, end, produce)."""
        spans = []
        i = 0
        while i < len(tokens):
            for size in range(min(MAX_PHRASE_WORDS, len(tokens) - i), 0, -1):
                phrase = " ".join(tokens[i : i + size])
                if phrase in self._lookup:
                    spans.append((i, i + size, self._lookup[phrase]))
                    i += size
                    break
            else:
                i += 1
        return spans


def build_lookup(aliases: Iterable[tuple[str, str]]) -> dict[str, str]:
    """Normalised phrase -> canonical produce name.

    Raises if two aliases normalise to the same phrase but point at different produce
    (e.g. "date" and "dates" mapped to different rows) - the lookup would silently
    keep whichever came last.
    """
    lookup: dict[str, str] = {}
    for alias, canonical in aliases:
        key = normalise_text(alias)
        if lookup.get(key, canonical) != canonical:
            raise ValueError(
                f"Alias {alias!r} normalises to {key!r}, which already maps to "
                f"{lookup[key]!r}, not {canonical!r}"
            )
        lookup[key] = canonical
    return lookup


def split_chunks(line: str) -> list[str]:
    for separator in CHUNK_SEPARATORS:
        line = line.replace(separator, "\n")
    return [chunk for chunk in line.split("\n") if chunk.strip()]


def first_in(tokens: list[str], words: set[str]) -> str | None:
    return next((token for token in tokens if token in words), None)


@lru_cache(maxsize=1)
def default_matcher() -> ProduceMatcher:
    """Matcher built from the reviewed aliases in produce_alias. Built once per process (see
    lru_cache), so newly approved aliases are used after a restart.

    Unreviewed aliases (suggestions from Claude, see alias_store) are left out until approved.
    """
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute("""
            SELECT a.alias, p.name
            FROM produce_alias a
            JOIN produce p ON p.id = a.produce_id
            WHERE a.reviewed
        """)
        aliases = cursor.fetchall()

    return ProduceMatcher(aliases)


def match_lines(lines: list[str]) -> list[list[str]]:
    """One list of canonical produce names per input line, in the same order, using the alias table."""
    matcher = default_matcher()
    return [sorted(matcher.produce_in_line(line)) for line in lines]
