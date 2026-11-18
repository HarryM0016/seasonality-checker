"""Accuracy tests for the Claude (LLM) produce matcher, driven by tests/fixtures/*.json.

Each fixture is one scraped recipe:
    {"url": ..., "lines": [{"line": <raw scraped line>, "expected": [<produce names>]}]}

Run:
    pytest              # offline checks only (fixture validation)
    pytest -m llm       # also run the Claude matcher against every recipe (costs tokens)
"""

import json
from pathlib import Path

import pytest

from seasonality_checker.recipes.produce_matcher_llm import (
    get_produce_names,
    match_produce,
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


def format_failure(recipe: dict, missed: set[str], false_positives: set[str]) -> str:
    parts = [f"{recipe['id']} ({recipe['url']})"]
    if missed:
        parts.append(f"  missed produce:   {sorted(missed)}")
    if false_positives:
        parts.append(f"  false positives:  {sorted(false_positives)}")
    return "\n".join(parts)


# --- Offline: make sure the fixtures themselves are valid -------------------


@pytest.mark.parametrize("recipe", RECIPES, ids=lambda r: r["id"])
def test_fixture_labels_are_known_produce(recipe):
    unknown = expected_produce(recipe) - set(get_produce_names())
    assert (
        not unknown
    ), f"{recipe['id']} expects produce that isn't in the produce list: {sorted(unknown)}"


# --- Live: run the Claude matcher (costs tokens) --------------------------


@pytest.mark.llm
@pytest.mark.parametrize("recipe", RECIPES, ids=lambda r: r["id"])
def test_llm_matcher(recipe):
    raw_lines = [line["line"] for line in recipe["lines"]]

    actual = set(match_produce(raw_lines))
    missed, false_positives = compare(expected_produce(recipe), actual)

    assert not missed and not false_positives, format_failure(
        recipe, missed, false_positives
    )
