"""
ingest_prices.py — pulls historical asset price data from Yahoo Finance
via yfinance and writes OHLCV rows to the raw_prices SQLite table.

Usage:
    python scripts/ingest_prices.py
"""
import sqlite3
import yfinance as yf
import pandas as pd
from pathlib import Path
from config import TICKERS, DB_PATH, PRICE_START_DATE


def ingest_prices(db_path: str = DB_PATH) -> None:
    # TODO: download OHLCV for each ticker in TICKERS
    # TODO: write to raw_prices table (upsert on date + ticker)
    raise NotImplementedError


if __name__ == "__main__":
    ingest_prices()
