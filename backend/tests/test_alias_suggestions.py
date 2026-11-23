"""Tests for choosing which of Claude's phrases become alias suggestions.

Offline: uses a small in-memory alias list, no database or API key.

Run:
    pytest tests/test_alias_suggestions.py
"""

import pytest

from seasonality_checker.matching.alias_suggestions import find_suggestions, is_new_alias
from seasonality_checker.matching.llm import LlmMatch
from seasonality_checker.matching.lookup import ProduceMatcher

KNOWN = ProduceMatcher(
    [
        ("raspberry", "raspberry"),
        ("lemon", "lemon"),
        ("lime", "lime"),
        ("spinach", "spinach"),
        ("passionfruit", "passionfruit"),
    ]
)


@pytest.mark.parametrize(
    "phrase, produce, line",
    [
        ("rasberries", "raspberry", "20 rasberries, halved"),  # misspelling
        ("Rasberries", "raspberry", "20 Rasberries"),  # case doesn't matter
        ("passsionfruit", "passionfruit", "See post for options (passsionfruit pulp, mango)"),
    ],
)
def test_suggested(phrase, produce, line):
    assert is_new_alias(phrase, produce, line, KNOWN)


@pytest.mark.parametrize(
    "phrase, produce, line",
    [
        ("", "raspberry", "20 rasberries"),
        ("fresh ripe red rasberries", "raspberry", "fresh ripe red rasberries"),  # > 3 words
        ("20 rasberries", "raspberry", "20 rasberries"),  # quantity
        ("frozen rasberries", "raspberry", "1 cup frozen rasberries"),  # exclude word
        ("rasberries", "raspberry", "1 cup blueberries"),  # not in the line
        ("rasberries lemon", "raspberry", "rasberries, lemon"),  # spans two chunks
        ("raspberries", "raspberry", "20 raspberries"),  # already an alias
        ("lemon", "lime", "1 lemon"),  # alias of other produce: would clash
        ("baby spinach", "spinach", "2 cups baby spinach"),  # lookup already finds it
    ],
    ids=[
        "empty",
        "too-long",
        "quantity",
        "exclude-word",
        "not-in-line",
        "across-chunks",
        "existing",
        "clash",
        "redundant",
    ],
)
def test_not_suggested(phrase, produce, line):
    assert not is_new_alias(phrase, produce, line, KNOWN)


def test_find_suggestions_stores_plain_words_once():
    lines = ["20 Rasberries,", "10 rasberry", "1 lemon"]
    matches = [
        [LlmMatch("raspberry", "Rasberries")],
        [LlmMatch("raspberry", "rasberry")],  # same alias once singularised
        [LlmMatch("lemon", "lemon")],  # already known
    ]

    assert find_suggestions(lines, matches, KNOWN) == [("rasberries", "raspberry")]
