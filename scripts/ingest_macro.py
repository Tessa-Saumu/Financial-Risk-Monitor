"""
ingest_macro.py — pulls macroeconomic indicators from the FRED REST API
and writes them to the raw_macro SQLite table.

Indicators configured in config.py (FRED_SERIES):
  FEDFUNDS, CPIAUCSL, UNRATE, DGS10, and others.

Usage:
    python scripts/ingest_macro.py
"""
import os
import requests
import sqlite3
import pandas as pd
from config import FRED_SERIES, DB_PATH


def ingest_macro(db_path: str = DB_PATH) -> None:
    fred_api_key = os.getenv("FRED_API_KEY")
    # TODO: for each series in FRED_SERIES, call FRED REST API
    # TODO: write to raw_macro table (upsert on date + indicator_name)
    raise NotImplementedError


if __name__ == "__main__":
    ingest_macro()
