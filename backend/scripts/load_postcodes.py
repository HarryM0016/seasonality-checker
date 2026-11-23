"""Load data/postcode_climate_mapping.csv (from build_postcode_climates.py) into the postcodes table.

Postcodes are read as text so leading zeros are kept ("0812", not 812).

Run:
    python scripts/load_postcodes.py
"""

from pathlib import Path

import pandas

from seasonality_checker.db import get_connection

CSV_PATH = Path(__file__).resolve().parents[1] / "data" / "postcode_climate_mapping.csv"


def main() -> None:
    dataframe = pandas.read_csv(CSV_PATH, dtype={"postcode": str})
    rows = [(row.postcode.zfill(4), row.climate) for row in dataframe.itertuples()]

    with get_connection() as connection, connection.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO postcodes (postcode, climate_id)
            SELECT %s, id FROM climates WHERE name = %s
            ON CONFLICT DO NOTHING
            """,
            rows,
        )

    print(f"Loaded {len(rows)} postcodes from {CSV_PATH}")


if __name__ == "__main__":
    main()
