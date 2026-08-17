"""Utility script: create the primary application database if it does not exist.

Usage (run from the backend/ directory):
    python create_db.py

Reads connection details from the same environment variables used by the app:
    PG_HOST, PG_PORT, PG_USER, PG_PASSWORD, PG_DATABASE
"""

import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()

PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = os.getenv("PG_PORT", "5432")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "")
PG_DATABASE = os.environ["PG_DATABASE"]  # required – no default


def create_database() -> None:
    # Connect to the default 'postgres' maintenance database to issue CREATE DATABASE
    conn = psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        user=PG_USER,
        password=PG_PASSWORD,
        dbname="postgres",
    )
    conn.autocommit = True
    cursor = conn.cursor()

    cursor.execute(
        "SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s",
        (PG_DATABASE,),
    )
    exists = cursor.fetchone()
    if not exists:
        cursor.execute(f'CREATE DATABASE "{PG_DATABASE}"')
        print(f"Database '{PG_DATABASE}' created.")
    else:
        print(f"Database '{PG_DATABASE}' already exists.")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    create_database()