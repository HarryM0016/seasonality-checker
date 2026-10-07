from src.seasonality_checker.recipes.ingredient_extractor import extract_ingredients_from_recipe
from src.seasonality_checker.recipes.ingredient_normalizer import normalise_ingredients
from src.seasonality_checker.seasonality_getter import get_seasonality
from src.seasonality_checker.recipe_scorer import score_recipe

if __name__ == "__main__":
    ingredients = extract_ingredients_from_recipe("https://cooking.nytimes.com/recipes/1008-guacamole")
    print(f"{ingredients}\n")
    
    normalised_ingredients = normalise_ingredients(ingredients)
    print(f"{normalised_ingredients}\n")
    
    updated_ingredients = get_seasonality(normalised_ingredients, 6)
    print(f"{score_recipe(updated_ingredients)}")