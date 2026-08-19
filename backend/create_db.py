"""Utility script: create the platform application databases if they do not exist.

Usage (run from the backend/ directory):
    python create_db.py

Reads connection details from the same environment variables used by the app:
    PG_HOST, PG_PORT, PG_USER, PG_PASSWORD, SYSTEM_DB_NAME, DATA_DB_NAME, ASSET_DB_NAME
"""

import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()

PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = os.getenv("PG_PORT", "5432")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "")

DATABASES = [
    os.getenv("SYSTEM_DB_NAME", "compassx_account"),
    os.getenv("DATA_DB_NAME", "compassx_system"),
    os.getenv("ASSET_DB_NAME", "asset_manager"),
]


def create_databases() -> None:
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

    for db_name in DATABASES:
        cursor.execute(
            "SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s",
            (db_name,),
        )
        exists = cursor.fetchone()
        if not exists:
            cursor.execute(f'CREATE DATABASE "{db_name}"')
            print(f"Database '{db_name}' created.")
        else:
            print(f"Database '{db_name}' already exists.")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    create_databases()