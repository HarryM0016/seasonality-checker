"""When produce is in season, and how seasonal a recipe is in each month.

    get_climate_id(postcode)            postcode -> climate zone
    get_seasonality(names, climate_id)  produce names -> their season ranges in that climate
    score_recipe(seasons)               season ranges -> a score for each month
"""

from dataclasses import dataclass

from seasonality_checker.db import get_connection


@dataclass(frozen=True)
class ProduceSeason:
    name: str
    season_start: int  # month, 1-12
    season_end: int  # month, 1-12; may be before season_start for seasons spanning New Year

    def is_in_season(self, month: int) -> bool:
        if self.season_start <= self.season_end:
            return self.season_start <= month <= self.season_end
        return month >= self.season_start or month <= self.season_end


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


def get_seasonality(produce_names: list[str], climate_id: int) -> list[ProduceSeason]:
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

    return [ProduceSeason(name, *ranges[name]) for name in produce_names if name in ranges]


def score_recipe(seasons: list[ProduceSeason]) -> list[float]:
    """A score for each month (index 0 = January): how much of the produce is in season,
    smoothed with half-weight from the neighbouring months."""
    counts = [
        sum(season.is_in_season(month) for season in seasons) for month in range(1, 13)
    ]
    return [
        round((0.5 * counts[month - 1] + counts[month] + 0.5 * counts[(month + 1) % 12]) / 3, 2)
        for month in range(12)
    ]
