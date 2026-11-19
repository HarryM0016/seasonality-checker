"""Opens the database connections.

When the FastAPI app exists, swap the body of get_connection() for a connection pool.
"""

import os
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg2
from dotenv import load_dotenv
from psycopg2.extensions import connection as Connection


@contextmanager
def get_connection() -> Iterator[Connection]:
    """Open a connection, commit if the block succeeds, roll back if it raises, always close.

    with get_connection() as connection, connection.cursor() as cursor:
        cursor.execute(...)
    """
    load_dotenv()
    connection = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
