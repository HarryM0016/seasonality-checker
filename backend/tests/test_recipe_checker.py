"""Tests for the recipe checker (orchestrator).

Everything outside the orchestrator - the recipe table, the scraper, both matchers and the
seasonality data - is replaced with small in-memory fakes, so these tests are free, fast
and need no database or API key.

Run:
    pytest tests/test_recipe_checker.py
"""

import pytest

from seasonality_checker.domain.ingredient import Ingredient
from seasonality_checker.recipes import recipe_checker, recipe_store
from seasonality_checker.recipes.recipe_checker import (
    InvalidRecheck,
    RecipeNotFound,
    UnknownPostcode,
    UnsupportedRecipe,
    check_recipe,
    normalise_url,
    recheck_lines,
)
from seasonality_checker.recipes.recipe_store import StoredLine, StoredRecipe

URL = "https://www.example.com/lemon-pasta/"

RECIPE_LINES = [
    "2 lemons, juiced",  # lookup finds lemon
    "200g spaghetti",  # nothing
    "20 rasberries",  # misspelt: lookup misses it
    "1 bunch testherb",  # lookup finds testherb (made up: has no seasonality data)
]

LOOKUP = {"2 lemons, juiced": ["lemon"], "1 bunch testherb": ["testherb"]}

SEASONS = {"lemon": (6, 9), "raspberry": (12, 2)}  # testherb deliberately missing


class Fakes:
    """In-memory replacements; records calls so tests can check what happened."""

    def __init__(self, monkeypatch):
        self.recipes: dict[int, StoredRecipe] = {}
        self.scraped: list[str] = []
        self.llm_calls: list[list[str]] = []
        self.llm_answers = {"20 rasberries": ["raspberry"]}
        self.page_lines = list(RECIPE_LINES)

        patch = monkeypatch.setattr
        patch(recipe_store, "get_by_url", self.get_by_url)
        patch(recipe_store, "get_by_id", self.recipes.get)
        patch(recipe_store, "insert", self.insert)
        patch(recipe_store, "save_llm_results", self.save_llm_results)
        patch(
            recipe_checker.ingredient_extractor,
            "extract_ingredients_from_recipe",
            self.scrape,
        )
        patch(recipe_checker.produce_matcher_lookup, "match_lines", self.lookup)
        patch(recipe_checker.produce_matcher_llm, "match_lines", self.llm)
        patch(recipe_checker.seasonality_getter, "get_climate_id", self.climate_id)
        patch(recipe_checker.seasonality_getter, "get_seasonality", self.seasonality)

    def get_by_url(self, url):
        return next((r for r in self.recipes.values() if r.url == url), None)

    def insert(self, url, texts):
        recipe = StoredRecipe(
            len(self.recipes) + 1, url, [StoredLine(t) for t in texts]
        )
        self.recipes[recipe.id] = recipe
        return recipe

    def save_llm_results(self, recipe_id, results):
        old = self.recipes[recipe_id]
        lines = [
            StoredLine(l.text, results.get(i, l.llm)) for i, l in enumerate(old.lines)
        ]
        self.recipes[recipe_id] = StoredRecipe(old.id, old.url, lines)
        return self.recipes[recipe_id]

    def scrape(self, url):
        self.scraped.append(url)
        return self.page_lines

    def lookup(self, lines):
        return [LOOKUP.get(line, []) for line in lines]

    def llm(self, lines):
        self.llm_calls.append(lines)
        return [self.llm_answers.get(line, []) for line in lines]

    def climate_id(self, postcode):
        return 6 if postcode == "3000" else None

    def seasonality(self, names, climate_id):
        return [Ingredient(name, SEASONS[name]) for name in names if name in SEASONS]


@pytest.fixture
def fakes(monkeypatch):
    return Fakes(monkeypatch)


def methods(result):
    return [line.method for line in result.lines]


# --- normalise_url -------------------------------------------------------------


@pytest.mark.parametrize(
    "url, expected",
    [
        (
            "https://www.recipetineats.com/pavlova/#recipe",
            "https://www.recipetineats.com/pavlova/",
        ),
        (
            "HTTPS://WWW.RecipeTinEats.com/pavlova/",
            "https://www.recipetineats.com/pavlova/",
        ),
        ("https://site.com/r/?utm_source=x&utm_medium=y", "https://site.com/r/"),
        ("https://site.com/r?id=5&fbclid=abc", "https://site.com/r?id=5"),
        ("  https://site.com/r  ", "https://site.com/r"),
    ],
)
def test_normalise_url(url, expected):
    assert normalise_url(url) == expected


# --- check_recipe --------------------------------------------------------------


def test_check_recipe_labels_each_line(fakes):
    result = check_recipe(URL, "3000", month=7)

    assert [line.produce for line in result.lines] == [["lemon"], [], [], ["testherb"]]
    assert methods(result) == ["lookup", "none", "none", "lookup"]
    assert fakes.llm_calls == []  # Claude is never called by a plain check


def test_check_recipe_reports_seasonality(fakes):
    result = check_recipe(URL, "3000", month=7)

    assert [(p.name, p.in_season) for p in result.produce] == [
        ("lemon", True),
        ("testherb", None),  # no data for this climate: shown, but not scored
    ]
    assert len(result.monthly_scores) == 12


def test_second_check_uses_stored_recipe(fakes):
    first = check_recipe(URL, "3000")
    second = check_recipe(URL + "#recipe", "3000")  # same recipe, different URL form

    assert fakes.scraped == [URL]
    assert second.recipe_id == first.recipe_id


def test_unknown_postcode_fails_before_scraping(fakes):
    with pytest.raises(UnknownPostcode):
        check_recipe(URL, "9999")
    assert fakes.scraped == []


def test_page_without_ingredients_is_not_stored(fakes):
    fakes.page_lines = []
    with pytest.raises(UnsupportedRecipe):
        check_recipe(URL, "3000")
    assert fakes.recipes == {}


def test_invalid_month_is_rejected(fakes):
    with pytest.raises(recipe_checker.RecipeCheckError):
        check_recipe(URL, "3000", month=13)


# --- recheck_lines -------------------------------------------------------------


def test_recheck_sends_only_selected_lines_to_claude(fakes):
    recipe_id = check_recipe(URL, "3000").recipe_id

    result = recheck_lines(recipe_id, [2, 1], "3000", month=1)

    assert fakes.llm_calls == [["200g spaghetti", "20 rasberries"]]  # sorted by index
    assert methods(result) == ["lookup", "llm", "llm", "lookup"]
    assert result.lines[1].produce == []  # checked, nothing found
    assert result.lines[2].produce == ["raspberry"]
    assert ("raspberry", True) in [(p.name, p.in_season) for p in result.produce]


@pytest.mark.parametrize(
    "claude_answer",
    [
        ["lime"],  # replaced, not merged: a merge would give ["lemon", "lime"]
        [],  # e.g. "Raspberry Coulis": Claude removes the lookup's false positive
    ],
    ids=["different-produce", "nothing"],
)
def test_claude_answer_replaces_lookup_for_that_line(fakes, claude_answer):
    fakes.llm_answers["2 lemons, juiced"] = claude_answer  # lookup finds ["lemon"]
    recipe_id = check_recipe(URL, "3000").recipe_id

    result = recheck_lines(recipe_id, [0], "3000")

    assert result.lines[0].produce == claude_answer
    assert result.lines[0].method == "llm"
    assert "lemon" not in [p.name for p in result.produce]  # gone from seasonality too


def test_recheck_results_are_kept_for_later_checks(fakes):
    recipe_id = check_recipe(URL, "3000").recipe_id
    recheck_lines(recipe_id, [2], "3000")

    later = check_recipe(URL, "3000")

    assert later.lines[2].produce == ["raspberry"]
    assert len(fakes.llm_calls) == 1  # no second Claude call


def test_recheck_unknown_recipe(fakes):
    with pytest.raises(RecipeNotFound):
        recheck_lines(42, [0], "3000")


@pytest.mark.parametrize(
    "indices",
    [
        [],
        [4],  # out of range (4 lines: 0-3)
        [-1],
        list(range(recipe_checker.MAX_RECHECK_LINES + 1)),
    ],
    ids=["none", "too-high", "negative", "too-many"],
)
def test_invalid_recheck_never_calls_claude(fakes, indices):
    fakes.page_lines = (
        [f"line {i}" for i in range(20)] if len(indices) > 4 else RECIPE_LINES
    )
    recipe_id = check_recipe(URL, "3000").recipe_id

    with pytest.raises(InvalidRecheck):
        recheck_lines(recipe_id, indices, "3000")
    assert fakes.llm_calls == []


def test_duplicate_indices_are_sent_once(fakes):
    recipe_id = check_recipe(URL, "3000").recipe_id
    recheck_lines(recipe_id, [2, 2, 2], "3000")
    assert fakes.llm_calls == [["20 rasberries"]]
