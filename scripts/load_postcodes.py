import psycopg2
import pandas
import os
from dotenv import load_dotenv

load_dotenv()
connection_string = os.getenv('DATABASE_URL')

connection = psycopg2.connect(connection_string)
cursor = connection.cursor()

dataframe = pandas.read_csv('postcode_climate_mapping.csv')

for _, row in dataframe.iterrows():
    try:
        cursor.execute(
            """
            INSERT INTO postcodes (postcode, climate_id)
            SELECT %s, id FROM climates WHERE name = %s
            ON CONFLICT DO NOTHING
        """, (row['postcode'], row['climate']))
    except Exception as e:
        print(f"Error inserting {row['postcode']}: {e}")

connection.commit()
cursor.close()
connection.close()