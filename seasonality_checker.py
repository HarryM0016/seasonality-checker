import psycopg2
import os
from dotenv import load_dotenv
from datetime import datetime

def check_seasonality(ingredients: list[list[str, bool]], climate_id: int):
    month = datetime.now().month
    
    load_dotenv()
    connection_string = os.getenv('DATABASE_URL')

    connection = psycopg2.connect(connection_string)
    cursor = connection.cursor()

    for ingredient in ingredients:
        cursor.execute(
            """
            SELECT in_season_start, in_season_end
            FROM produce_seasonality      
            WHERE produce_id = (SELECT id FROM produce WHERE name = %s)
            AND climate_id = %s    
            """, (ingredient[0], climate_id)
        )
        season_range = cursor.fetchone()
        if season_range[0] == 0:
            continue
        
        if is_in_season(month, season_range[0], season_range[1]):
            ingredient[1] = True
        
    return ingredients

def is_in_season(month: int, start: int, end: int) -> bool:
    if start <= end:
        return start <= month <= end
    return month >= start or month <= end
        
if __name__ == "__main__":
    ingredients = [['rhubarb', False], ['strawberry', False]]
    climate_id = 6
    print(check_seasonality(ingredients, climate_id))