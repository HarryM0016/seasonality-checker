"""Reads and writes the `recipe` table.

Each recipe is one row; `lines` is a JSONB array holding only what is slow or costly to redo:
    [{"text": "20 rasberries", "llm": ["raspberry"]}, {"text": "1 tbsp oil", "llm": null}]

"llm": null means the line was never sent to Claude; [] means Claude checked and found nothing.
Lookup results are NOT stored. They take milliseconds to recompute and would go stale
whenever the alias table changes.
"""

from dataclasses import dataclass

from psycopg2.extras import Json

from seasonality_checker.db import get_connection


@dataclass(frozen=True)
class StoredLine:
    text: str
    llm: list[str] | None = None


@dataclass(frozen=True)
class StoredRecipe:
    id: int
    url: str
    lines: list[StoredLine]


def get_by_url(url: str) -> StoredRecipe | None:
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT id, url, lines FROM recipe WHERE url = %s", (url,))
        row = cursor.fetchone()
    return _to_recipe(row) if row else None


def get_by_id(recipe_id: int) -> StoredRecipe | None:
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT id, url, lines FROM recipe WHERE id = %s", (recipe_id,))
        row = cursor.fetchone()
    return _to_recipe(row) if row else None


def insert(url: str, texts: list[str]) -> StoredRecipe:
    """Store a newly scraped recipe.

    If another request stored the same URL in the meantime, the existing row is returned
    unchanged (the no-op UPDATE is what makes RETURNING give back the existing row).
    """
    lines = [StoredLine(text) for text in texts]
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO recipe (url, lines) VALUES (%s, %s)
            ON CONFLICT (url) DO UPDATE SET url = EXCLUDED.url
            RETURNING id, url, lines
            """,
            (url, Json(_to_json(lines))),
        )
        row = cursor.fetchone()
    return _to_recipe(row)


def save_llm_results(recipe_id: int, results: dict[int, list[str]]) -> StoredRecipe:
    """Record Claude's results for some lines, keyed by line index.

    The row is locked while it's updated, so two rechecks of the same recipe at the same
    time can't overwrite each other's results. (Claude is called before this, so the lock
    is only held for the read and write, not the API call.)
    """
    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, url, lines FROM recipe WHERE id = %s FOR UPDATE", (recipe_id,)
        )
        row = cursor.fetchone()
        if row is None:
            raise LookupError(f"recipe {recipe_id} not found")

        recipe = _to_recipe(row)
        lines = [
            StoredLine(line.text, results[index]) if index in results else line
            for index, line in enumerate(recipe.lines)
        ]
        cursor.execute(
            "UPDATE recipe SET lines = %s WHERE id = %s",
            (Json(_to_json(lines)), recipe_id),
        )
    return StoredRecipe(recipe.id, recipe.url, lines)


def _to_recipe(row: tuple) -> StoredRecipe:
    recipe_id, url, lines = row  # psycopg2 decodes JSONB into Python lists/dicts
    return StoredRecipe(
        recipe_id, url, [StoredLine(line["text"], line.get("llm")) for line in lines]
    )


def _to_json(lines: list[StoredLine]) -> list[dict]:
    return [{"text": line.text, "llm": line.llm} for line in lines]
