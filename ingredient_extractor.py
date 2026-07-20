from urllib.request import urlopen
from dotenv import load_dotenv
from anthropic import Anthropic
import recipe_scrapers
import json
import os

load_dotenv()

def extract_ingredients_from_recipe(url: str) -> list[str]:
    html = urlopen(url).read().decode("utf-8")
    
    try:
        scraper = recipe_scrapers.scrape_html(html, org_url=url)
    except recipe_scrapers._exceptions.WebsiteNotImplementedError:
        ingredients = []
        print("Website not supported")
        return ingredients
    
    ingredients = scraper.ingredients()
    
    return ingredients

def normalise_ingredients(ingredients: list[str]) -> list[str]:
    allowed_produce_list = [
        "apple", "apricot", "artichoke", "asparagus", "avocado", 
        "banana", "basil", "beetroot", "blackberry", "blueberry", 
        "bok choy", "broad beans", "broccoli", "brussel sprouts", "cabbage", 
        "cantaloupe", "capsicum", "carrot", "cauliflower", "celery",
        "cherry", "chestnut", "chilli", "chinese broccoli", "coconut",
        "coriander", "corn", "cucumber", "cumquat", "custard apple",
        "date", "dill", "dragonfruit", "eggplant", "fennel",
        "figs", "garlic", "ginger", "granny smith apple", "grapefruit", 
        "grapes", "green beans", "honeydew melon", "kale", "kiwifruit",
        "leek", "lemon", "lettuce", "lime", "lychee", 
        "mandarin", "mango", "mint", "mushroom", "nectarine", 
        "onion", "orange", "parsley", "parsnip", "passionfruit", 
        "peach", "pear", "peas", "persimmon", "pineapple", 
        "plum", "pomegrante", "potato", "pumpkin", "quince", 
        "radish", "raspberry", "rhubarb", "rocket", "silverbeet", 
        "snow peas", "spinach", "spring onion", "squash", "strawberry",
        "sweet potato", "tomato", "turnip", "watermelon", "zucchini"
    ]
    
    client = Anthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY")
    )
    
    system_prompt = f"""
    You are a precise culinary data normalization assistant.
    Extract ONLY the fresh produce items from the raw recipe list that match this database list:
    {json.dumps(allowed_produce_list)}
    
    Normalize them to the exact strings provided above. Non-produce items must be ignored.
    """
    
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1000,
        temperature=0.0,
        system=system_prompt,
        messages=[
            {"role": "user", "content": f"Raw Recipe Ingredients: {json.dumps(ingredients)}"}
        ],
        tools=[
            {
                "name": "return_normalized_ingredients",
                "description": "Returns the list of matching, normalized ingredients.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "matched_ingredients": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of normalized ingredient names matching the database."
                        }
                    },
                    "required": ["matched_ingredients"]
                }
            }
        ],
        tool_choice={"type": "tool", "name": "return_normalized_ingredients"}
    )
    
    tool_use = response.content[0]
    result = tool_use.input
    return result.get("matched_ingredients", [])
    
if __name__ == "__main__":
    # url = "https://www.recipetineats.com/apple-pie-recipe/"
    # url = "https://www.andy-cooks.com/blogs/recipes/pico-de-gallo?_pos=1&_sid=7f33eaca6&_ss=r"
    url = "https://cooking.nytimes.com/recipes/6216-strawberry-rhubarb-pie"
    ingredients = extract_ingredients_from_recipe(url)
    parsed_data = normalise_ingredients(ingredients)
    print(parsed_data)