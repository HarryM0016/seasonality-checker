"""Saves Claude's matches as suggested aliases, so the lookup can learn new names.

When Claude finds produce in a line, it also returns the words that named it
("20 rasberries" -> raspberry, phrase "rasberries"). New phrases are stored in produce_alias
with source = 'llm' and reviewed = false. The lookup only uses reviewed aliases, so a
suggestion does nothing until you approve it:

    SELECT alias, produce_name, created_at FROM produce_alias WHERE NOT reviewed;
    UPDATE produce_alias SET reviewed = true WHERE alias = 'rasberries';   -- approve
    DELETE FROM produce_alias WHERE alias = '...';                          -- reject

The lookup is built once per process, so approved aliases are used after a restart.
"""

from seasonality_checker.db import get_connection
from seasonality_checker.recipes.produce_matcher_llm import LlmMatch
from seasonality_checker.recipes.produce_matcher_lookup import (
    EXCLUDE_AFTER,
    EXCLUDE_BEFORE,
    MAX_PHRASE_WORDS,
    ProduceMatcher,
    split_chunks,
)
from seasonality_checker.recipes.text_normaliser import normalise_text, split_words, tokenise

_EXCLUDED_WORDS = {normalise_text(word) for word in EXCLUDE_BEFORE | EXCLUDE_AFTER}


def save_suggestions(lines: list[str], matches: list[list[LlmMatch]]) -> list[tuple[str, str]]:
    """Store the new aliases in Claude's matches for these lines. Returns the (alias, produce) added."""
    with get_connection() as connection, connection.cursor() as cursor:
        # Every alias, reviewed or not: a suggestion must not clash with a pending one either
        cursor.execute(
            "SELECT a.alias, p.name FROM produce_alias a JOIN produce p ON p.id = a.produce_id"
        )
        known = ProduceMatcher(cursor.fetchall())

        suggestions = find_suggestions(lines, matches, known)
        if not suggestions:
            return []

        aliases, produce = zip(*suggestions)
        cursor.execute(
            """
            INSERT INTO produce_alias (alias, produce_id, produce_name, source, reviewed)
            SELECT s.alias, p.id, p.name, 'llm', false
            FROM unnest(%s::text[], %s::text[]) AS s(alias, produce)
            JOIN produce p ON p.name = s.produce
            ON CONFLICT (alias) DO NOTHING
            RETURNING alias, produce_name
            """,
            (list(aliases), list(produce)),
        )
        return cursor.fetchall()


def find_suggestions(
    lines: list[str], matches: list[list[LlmMatch]], known: ProduceMatcher
) -> list[tuple[str, str]]:
    """(alias, produce) pairs worth suggesting, at most one per normalised alias."""
    suggestions: dict[str, tuple[str, str]] = {}
    for line, line_matches in zip(lines, matches):
        for match in line_matches:
            key = normalise_text(match.phrase)
            if key not in suggestions and is_new_alias(match.phrase, match.produce, line, known):
                suggestions[key] = (" ".join(split_words(match.phrase)), match.produce)
    return list(suggestions.values())


def is_new_alias(phrase: str, produce: str, line: str, known: ProduceMatcher) -> bool:
    """Whether Claude's phrase is safe and useful to add as an alias for `produce`.

    Rejected:
      - empty, or longer than the lookup can match (MAX_PHRASE_WORDS)
      - contains a number ("20 rasberries") or an exclude word ("frozen rasberries")
      - not actually in the line (within one chunk, the way the lookup reads it)
      - already an alias, for this or any other produce: a clash would break the lookup
      - redundant: the lookup already finds this produce in it ("baby spinach")
    """
    tokens = tokenise(phrase)
    if not 1 <= len(tokens) <= MAX_PHRASE_WORDS:
        return False
    if any(any(char.isdigit() for char in token) or token in _EXCLUDED_WORDS for token in tokens):
        return False
    if not any(_contains(tokenise(chunk), tokens) for chunk in split_chunks(line)):
        return False
    if known.canonical_for(phrase) is not None:
        return False
    if produce in known.produce_in_line(phrase):
        return False
    return True


def _contains(tokens: list[str], phrase: list[str]) -> bool:
    size = len(phrase)
    return any(tokens[i : i + size] == phrase for i in range(len(tokens) - size + 1))
