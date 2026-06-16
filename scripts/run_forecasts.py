"""
run_forecasts.py — runs a Prophet forecasting model per asset,
generating a 30-day price outlook with upper and lower confidence bounds.
Writes results to the forecasts SQLite table.

Usage:
    python scripts/run_forecasts.py
"""
import sqlite3
import pandas as pd
from prophet import Prophet
from config import TICKERS, DB_PATH, FORECAST_HORIZON_DAYS


def run_forecasts(db_path: str = DB_PATH) -> None:
    # TODO: for each ticker, fit Prophet model on historical close prices
    # TODO: generate FORECAST_HORIZON_DAYS forward predictions
    # TODO: write predicted_close, lower_bound, upper_bound to forecasts table
    raise NotImplementedError


if __name__ == "__main__":
    run_forecasts()
