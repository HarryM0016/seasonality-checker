from src.seasonality_checker.seasonality_getter import Ingredient

def score_recipe(ingredients: list[Ingredient]):
    score = [0] * 12
    averaged_score = [0] * 12
    
    for month in range(12):
        for ingredient in ingredients:
            if ingredient.is_in_season(month + 1):
                score[month] += 1
    
    for month in range(12):
        averaged_score[month] = round(((0.5 * score[month - 1] + score[month] + 0.5 * score[(month + 1) % 12]) / 3), 2)
    
    return averaged_score