import argparse

from seasonality_checker.recipes.ingredient_extractor import extract_ingredients_from_recipe
from seasonality_checker.recipes.ingredient_normalizer import normalise_ingredients
from seasonality_checker.seasonality_getter import get_seasonality
from seasonality_checker.recipe_scorer import score_recipe

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "url",
        nargs="?",
        default="https://cooking.nytimes.com/recipes/1008-guacamole",
    )
    args = parser.parse_args()

    url = args.url
    ingredients = extract_ingredients_from_recipe(url)
    print(f"{ingredients}\n")
    
    normalised_ingredients = normalise_ingredients(ingredients)
    print(f"{normalised_ingredients}\n")
    
    updated_ingredients = get_seasonality(normalised_ingredients, 6)
    print(f"{score_recipe(updated_ingredients)}")