"""HTTP retry policy for a pull. Values match the executor."""
import os

MAX_PAGES_DEFAULT = int(os.environ.get("INGESTION_MAX_PAGES", "500"))
BACKOFF_BASE = 1.0
BACKOFF_MAX = 60.0
MAX_ATTEMPTS_429 = 5
MAX_ATTEMPTS_5XX = 3
