"""Checks a recipe: the two entry points the API routes will call.

    check_recipe(url, postcode)                 scrape (or load) -> lookup -> seasonality -> score
    recheck_lines(recipe_id, indices, postcode) Claude on the lines the user selected -> save -> same result

The lookup runs on every request (it's fast and picks up new aliases). Scraped text and
Claude's results are stored in the `recipe` table, since those are slow or cost money.
Seasonality and scores depend on the user's postcode and month, so they're never stored.
"""

from dataclasses import dataclass
from datetime import date
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from seasonality_checker import recipe_scorer, seasonality_getter
from seasonality_checker.recipes import (
    alias_store,
    ingredient_extractor,
    produce_matcher_llm,
    produce_matcher_lookup,
    recipe_store,
)

MAX_RECHECK_LINES = 10

TRACKING_PARAMS = {"fbclid", "gclid", "mc_cid", "mc_eid"}


# --- Errors (the API will turn these into 4xx responses) -----------------------


class RecipeCheckError(Exception):
    """Base class: something about the request is wrong, not the server."""


class UnknownPostcode(RecipeCheckError):
    pass


class UnsupportedRecipe(RecipeCheckError):
    """The page couldn't be scraped, or it has no ingredient list."""


class RecipeNotFound(RecipeCheckError):
    pass


class InvalidRecheck(RecipeCheckError):
    pass


# --- Results -------------------------------------------------------------------


@dataclass(frozen=True)
class LineResult:
    index: int
    text: str
    produce: list[str]
    method: Literal[
        "lookup", "llm", "none"
    ]  # "llm": Claude checked it (produce may be [])


@dataclass(frozen=True)
class ProduceResult:
    name: str
    in_season: bool | None  # None: no seasonality data for this climate


@dataclass(frozen=True)
class RecipeResult:
    recipe_id: int
    url: str
    month: int
    lines: list[LineResult]
    produce: list[ProduceResult]
    monthly_scores: list[float]  # index 0 = January


# --- Entry points ----------------------------------------------------------------


def check_recipe(url: str, postcode: str, month: int | None = None) -> RecipeResult:
    climate_id = _climate_for(postcode)  # validate before doing any slow work
    month = _validate_month(month)
    url = normalise_url(url)

    stored = recipe_store.get_by_url(url)
    if stored is None:
        texts = ingredient_extractor.extract_ingredients_from_recipe(url)
        if not texts:
            raise UnsupportedRecipe(f"No ingredients found at {url}")
        stored = recipe_store.insert(url, texts)

    return _build_result(stored, climate_id, month)


def recheck_lines(
    recipe_id: int, indices: list[int], postcode: str, month: int | None = None
) -> RecipeResult:
    climate_id = _climate_for(postcode)
    month = _validate_month(month)

    stored = recipe_store.get_by_id(recipe_id)
    if stored is None:
        raise RecipeNotFound(f"Recipe {recipe_id} not found")

    indices = sorted(set(indices))
    if not indices:
        raise InvalidRecheck("Select at least one line")
    if len(indices) > MAX_RECHECK_LINES:
        raise InvalidRecheck(f"Select at most {MAX_RECHECK_LINES} lines")
    if indices[0] < 0 or indices[-1] >= len(stored.lines):
        raise InvalidRecheck("Line index out of range")

    texts = [stored.lines[i].text for i in indices]
    matches = produce_matcher_llm.match_lines(texts)
    stored = recipe_store.save_llm_results(
        recipe_id,
        {
            index: [match.produce for match in found]
            for index, found in zip(indices, matches)
        },
    )

    alias_store.save_suggestions(texts, matches)

    return _build_result(stored, climate_id, month)


# --- Helpers ----------------------------------------------------------------------


def normalise_url(url: str) -> str:
    """One cache key per recipe: drop the #fragment and tracking parameters, lowercase the host.

    "HTTPS://www.RecipeTinEats.com/pavlova/?utm_source=x#recipe" -> "https://www.recipetineats.com/pavlova/"
    """
    parts = urlsplit(url.strip())
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in TRACKING_PARAMS
    ]
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path or "/",
            urlencode(query),
            "",
        )
    )


def _climate_for(postcode: str) -> int:
    climate_id = seasonality_getter.get_climate_id(postcode)
    if climate_id is None:
        raise UnknownPostcode(f"Unknown postcode: {postcode!r}")
    return climate_id


def _validate_month(month: int | None) -> int:
    if month is None:
        return date.today().month
    if not 1 <= month <= 12:
        raise RecipeCheckError("Month must be between 1 and 12")
    return month


def _build_result(
    stored: recipe_store.StoredRecipe, climate_id: int, month: int
) -> RecipeResult:
    lookup_matches = produce_matcher_lookup.match_lines(
        [line.text for line in stored.lines]
    )

    lines = []
    for index, (line, found) in enumerate(zip(stored.lines, lookup_matches)):
        if (
            line.llm is not None
        ):  # the user asked Claude to check this line; its answer wins
            lines.append(LineResult(index, line.text, line.llm, "llm"))
        elif found:
            lines.append(LineResult(index, line.text, found, "lookup"))
        else:
            lines.append(LineResult(index, line.text, [], "none"))

    # Unique produce across the recipe, in the order it first appears
    produce_names = list(dict.fromkeys(name for line in lines for name in line.produce))

    ingredients = seasonality_getter.get_seasonality(produce_names, climate_id)
    by_name = {ingredient.name: ingredient for ingredient in ingredients}
    produce = [
        ProduceResult(
            name, by_name[name].is_in_season(month) if name in by_name else None
        )
        for name in produce_names
    ]

    return RecipeResult(
        recipe_id=stored.id,
        url=stored.url,
        month=month,
        lines=lines,
        produce=produce,
        monthly_scores=recipe_scorer.score_recipe(ingredients),
    )
