"""Accuracy tests for the Claude (LLM) produce matcher, driven by tests/fixtures/*.json.

Each fixture is one scraped recipe:
    {"url": ..., "lines": [{"line": <raw scraped line>, "expected": [<produce names>]}]}

The live test mirrors how the app uses Claude: as a fallback for lines the lookup matcher
found nothing (or not everything) in. Those lines are a mix of real misses (misspellings, unusual names) and
true negatives (pine nuts, "Raspberry Coulis"), which is what users will tick and send.

Run:
    pytest              # offline checks only (fixture validation, response parsing)
    pytest -m llm       # also run Claude on each recipe's fallback lines (costs tokens, needs DATABASE_URL)
"""

import json
from pathlib import Path

import pytest

from seasonality_checker.recipes import produce_matcher_lookup
from seasonality_checker.recipes.produce_matcher_llm import (
    get_produce_names,
    match_lines,
    parse_results,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_recipes() -> list[dict]:
    recipes = []
    for path in sorted(FIXTURES_DIR.glob("*.json")):
        recipe = json.loads(path.read_text())
        recipe["id"] = path.stem
        recipes.append(recipe)
    return recipes


RECIPES = load_recipes()


def expected_produce(recipe: dict) -> set[str]:
    return {name for line in recipe["lines"] for name in line["expected"]}


def compare(expected: set[str], actual: set[str]) -> tuple[set[str], set[str]]:
    """Return (missed, false_positives)."""
    return expected - actual, actual - expected


# --- Offline: make sure the fixtures themselves are valid -------------------


@pytest.mark.parametrize("recipe", RECIPES, ids=lambda r: r["id"])
def test_fixture_labels_are_known_produce(recipe):
    unknown = expected_produce(recipe) - set(get_produce_names())
    assert (
        not unknown
    ), f"{recipe['id']} expects produce that isn't in the produce list: {sorted(unknown)}"


# --- Offline: parsing Claude's tool input ------------------------------------


def test_parse_results_fills_missing_lines():
    assert parse_results({"results": [{"index": 1, "produce": ["lime"]}]}, 3) == [[], ["lime"], []]


def test_parse_results_ignores_out_of_range_indices():
    tool_input = {"results": [{"index": 5, "produce": ["lime"]}, {"index": -1, "produce": ["lemon"]}]}
    assert parse_results(tool_input, 2) == [[], []]


def test_parse_results_merges_repeated_indices():
    tool_input = {
        "results": [
            {"index": 0, "produce": ["lime", "lemon"]},
            {"index": 0, "produce": ["lemon", "mint"]},
        ]
    }
    assert parse_results(tool_input, 1) == [["lime", "lemon", "mint"]]


# --- Live: run the Claude matcher (costs tokens) ------------------------------


def fallback_lines(recipe: dict) -> list[dict]:
    """The fixture lines a user could send to the fallback:

    - lines the lookup matcher found nothing in ("pine nuts", "20 rasberries"), and
    - lines where it found some produce but missed some ("mango" found, "passsionfruit" missed).
    """
    raw_lines = [line["line"] for line in recipe["lines"]]
    lookup_results = produce_matcher_lookup.match_lines(raw_lines)
    return [
        line
        for line, found in zip(recipe["lines"], lookup_results)
        if not found or set(line["expected"]) - set(found)
    ]


@pytest.mark.llm
@pytest.mark.parametrize("recipe", RECIPES, ids=lambda r: r["id"])
def test_llm_fallback(recipe):
    """One API call per recipe, on its fallback lines; all mismatches are reported together."""
    lines = fallback_lines(recipe)
    if not lines:
        pytest.skip("the lookup fully matched every line")

    actual = match_lines([line["line"] for line in lines])
    assert len(actual) == len(lines)

    failures = []
    for line, got in zip(lines, actual):
        missed, false_positives = compare(set(line["expected"]), set(got))
        if missed or false_positives:
            failures.append(
                f"  {line['line']!r}\n"
                f"      missed: {sorted(missed)}  false positives: {sorted(false_positives)}"
            )

    assert not failures, (
        f"{recipe['id']}: {len(failures)} of {len(lines)} fallback lines wrong ({recipe['url']})\n"
        + "\n".join(failures)
    )
