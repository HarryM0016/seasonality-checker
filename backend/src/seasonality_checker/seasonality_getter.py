from seasonality_checker.db import get_connection
from seasonality_checker.domain.ingredient import Ingredient


def get_climate_id(postcode: str) -> int | None:
    """Climate for an Australian postcode, or None if the postcode isn't known.

    Postcodes were loaded without their leading zero ("812" instead of "0812"), so both
    sides are padded to 4 digits; this keeps working once the data is fixed.
    """
    postcode = postcode.strip()
    if not (postcode.isdigit() and len(postcode) <= 4):
        return None

    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT climate_id FROM postcodes WHERE lpad(postcode, 4, '0') = %s",
            (postcode.zfill(4),),
        )
        row = cursor.fetchone()
    return row[0] if row else None


def get_seasonality(produce_names: list[str], climate_id: int) -> list[Ingredient]:
    """Season ranges for the given produce in one climate, in the order given.

    Produce with no seasonality row for this climate is left out, rather than crashing.
    """
    if not produce_names:
        return []

    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT p.name, s.in_season_start, s.in_season_end
            FROM produce_seasonality s
            JOIN produce p ON p.id = s.produce_id
            WHERE p.name = ANY(%s) AND s.climate_id = %s
            """,
            (list(produce_names), climate_id),
        )
        ranges = {name: (start, end) for name, start, end in cursor.fetchall()}

    return [Ingredient(name, ranges[name]) for name in produce_names if name in ranges]
