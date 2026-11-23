"""Accuracy and behaviour tests for the lookup (alias table) produce matcher.

Fixture tests check every line in tests/fixtures/*.json:
    {"url": ..., "lines": [{"line": <raw scraped line>, "expected": [<produce names>]}]}
Unit tests check individual matching rules against a small in-memory alias list.

Run:
    pytest tests/test_matching_lookup.py        # needs DATABASE_URL (reads produce_alias)
    pytest tests/test_matching_lookup.py -k "not fixture_line"   # unit tests only, no database needed
"""

import json
from pathlib import Path

import pytest

from seasonality_checker.matching.lookup import (
    ProduceMatcher,
    match_lines,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_lines() -> list:
    """One pytest case per fixture line.

    A line with "skip": ["lookup"] in its fixture is reported as skipped, not run - use it for
    lines only the LLM fallback is expected to handle, such as misspellings.
    """
    cases = []
    for path in sorted(FIXTURES_DIR.glob("*.json")):
        recipe = json.loads(path.read_text())
        for index, line in enumerate(recipe["lines"]):
            case = {"recipe": path.stem, "index": index, **line}
            marks = (
                [pytest.mark.skip(reason="fixture marks this line as LLM-only")]
                if "lookup" in line.get("skip", [])
                else []
            )
            cases.append(pytest.param(case, marks=marks))
    return cases


# --- Accuracy against the labelled fixtures, one test per scraped line ------


@pytest.mark.parametrize(
    "case", load_lines(), ids=lambda c: f"{c['recipe']}[{c['index']}] {c['line'][:40]}"
)
def test_fixture_line(case):
    [matches] = match_lines([case["line"]])
    actual = set(matches)
    expected = set(case["expected"])

    missed, false_positives = expected - actual, actual - expected
    assert not missed and not false_positives, (
        f"{case['line']!r}\n"
        f"  missed:          {sorted(missed)}\n"
        f"  false positives: {sorted(false_positives)}"
    )


# --- Behaviour of individual rules -------------------------------------------


@pytest.fixture
def matcher():
    names = [
        "red onion",
        "brown onion",
        "spring onion",
        "potato",
        "sweet potato",
        "coconut",
        "peas",
        "lemon",
        "lime",
    ]
    return ProduceMatcher(
        [(name, name) for name in names]
        + [("green onion", "spring onion"), ("onion", "brown onion")]
    )


def test_longest_match_wins(matcher):
    assert matcher.produce_in_line("1 sweet potato") == {"sweet potato"}
    assert matcher.produce_in_line("2 green onions") == {"spring onion"}


def test_falls_back_to_shorter_phrase(matcher):
    assert matcher.produce_in_line("1 large red onion") == {"red onion"}


def test_plurals_match(matcher):
    assert matcher.produce_in_line("3 potatoes") == {"potato"}
    assert matcher.produce_in_line("a handful of pea") == {"peas"}


def test_finds_every_item_in_a_line(matcher):
    assert matcher.produce_in_line("lemon, lime and onion") == {
        "lemon",
        "lime",
        "brown onion",
    }


def test_exclude_before(matcher):
    [match] = matcher.match_line("1 cup frozen peas")
    assert match.produce == "peas" and match.excluded_by == "frozen"


def test_exclude_after(matcher):
    assert matcher.produce_in_line("1 tsp onion powder") == set()


def test_exclusion_doesnt_cross_chunks(matcher):
    assert matcher.produce_in_line("1 lemon, salt to taste") == {"lemon"}


def test_exclusion_stops_at_next_match(matcher):
    # "oil" describes the coconut, not the lemon before it
    assert matcher.produce_in_line("lemon or coconut oil") == {"lemon"}


def test_conflicting_aliases_are_rejected():
    with pytest.raises(ValueError, match="date"):
        ProduceMatcher([("date", "date"), ("dates", "fig")])
