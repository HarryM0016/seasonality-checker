import psycopg2
import os
from dotenv import load_dotenv

class Ingredient:
    
    def __init__(self, name: str, seasonal_range: tuple):
        self.name = name
        self.season_start = seasonal_range[0]
        self.season_end = seasonal_range[1]
    
    def is_in_season(self, month: int) -> bool:
        if self.season_start <= self.season_end:
            return self.season_start <= month <= self.season_end
        return month >= self.season_start or month <= self.season_end
    

def get_seasonality(matched_ingredients: list[str], climate_id: int) -> list[Ingredient]:
    updated_ingredients = []
    
    load_dotenv()
    connection_string = os.getenv('DATABASE_URL')

    connection = psycopg2.connect(connection_string)
    cursor = connection.cursor()

    for ingredient in matched_ingredients:
        cursor.execute(
            """
            SELECT in_season_start, in_season_end
            FROM produce_seasonality      
            WHERE produce_id = (SELECT id FROM produce WHERE name = %s)
            AND climate_id = %s    
            """, (ingredient, climate_id)
        )
        season_range = cursor.fetchone()
        updated_ingredients.append(Ingredient(ingredient, season_range))
        
    return updated_ingredients