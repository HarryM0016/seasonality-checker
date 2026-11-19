import argparse

from seasonality_checker.recipes.ingredient_extractor import (
    extract_ingredients_from_recipe,
)
from seasonality_checker.recipes import produce_matcher_llm, produce_matcher_lookup
from seasonality_checker.seasonality_getter import get_seasonality
from seasonality_checker.recipe_scorer import score_recipe

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "url",
        nargs="?",
        default="https://cooking.nytimes.com/recipes/1008-guacamole",
    )
    parser.add_argument(
        "--llm", action="store_true", help="match with Claude instead of the alias table (costs tokens)"
    )
    args = parser.parse_args()

    matcher = produce_matcher_llm if args.llm else produce_matcher_lookup

    lines = extract_ingredients_from_recipe(args.url)
    matches = matcher.match_lines(lines)

    for index, (line, produce) in enumerate(zip(lines, matches)):
        label = ", ".join(produce) if produce else "-"
        print(f"{index:>3}  {label:<25}  {line}")

    # Unique produce across the recipe, in first-seen order
    produce_names = list(dict.fromkeys(name for line_matches in matches for name in line_matches))
    print(f"\n{produce_names}\n")

    updated_ingredients = get_seasonality(produce_names, 6)
    print(f"{score_recipe(updated_ingredients)}")
