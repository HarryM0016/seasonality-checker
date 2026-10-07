import json
import os

from anthropic import Anthropic
from dotenv import load_dotenv


ALLOWED_PRODUCE = [
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


def normalise_ingredients(ingredients: list[str]) -> list[str]:
    load_dotenv()
    client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    system_prompt = f"""
    You are a precise culinary data normalization assistant.
    Extract ONLY the fresh produce items from the raw recipe list that match this database list:
    {json.dumps(ALLOWED_PRODUCE)}

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
