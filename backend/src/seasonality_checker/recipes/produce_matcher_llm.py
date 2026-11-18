import json
import os
from functools import lru_cache

import psycopg2
from anthropic import Anthropic
from dotenv import load_dotenv


@lru_cache(maxsize=1)
def get_produce_names() -> list[str]:
    """Canonical produce names from the database, sorted so the prompt is identical every call."""
    load_dotenv()
    connection = psycopg2.connect(os.getenv("DATABASE_URL"))
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT name FROM produce ORDER BY name")
            return [name for (name,) in cursor.fetchall()]
    finally:
        connection.close()


def match_produce(lines: list[str]) -> list[str]:
    """Canonical names of the fresh produce in a recipe's ingredient lines, using Claude."""
    load_dotenv()
    client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    allowed_produce = get_produce_names()

    system_prompt = f"""
    You are a precise culinary data normalization assistant.
    Extract ONLY the fresh produce items from the raw recipe list that match this database list:
    {json.dumps(allowed_produce)}

    Normalize them to the exact strings provided above. Non-produce items must be ignored.
    """

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1000,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": f"Raw Recipe Ingredients: {json.dumps(lines)}",
            }
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
                            "items": {"type": "string", "enum": allowed_produce},
                            "description": "List of normalized ingredient names matching the database.",
                        }
                    },
                    "required": ["matched_ingredients"],
                },
            }
        ],
        tool_choice={"type": "tool", "name": "return_normalized_ingredients"},
    )

    tool_use = response.content[0]
    result = tool_use.input
    return result.get("matched_ingredients", [])
