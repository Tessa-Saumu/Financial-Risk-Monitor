"""
run_forecasts.py — runs a Prophet forecasting model per asset,
generating a 30-day price outlook with upper and lower confidence bounds.
Writes results to the forecasts SQLite table.

Usage:
    python -m scripts.run_forecasts
"""
import sqlite3
from datetime import date, timedelta

import pandas as pd

from config import (
    DB_PATH,
    TICKERS,
    ASSET_CLASS,
    FORECAST_HORIZON_DAYS,
    MIN_ROWS_FOR_FORECAST,
    PROPHET_INTERVAL_WIDTH,
    CHANGEPOINT_PRIOR_SCALE_BY_ASSET_CLASS,
)
from models.prophet.forecast import fit_and_forecast
# Reused rather than redefined — compute_risk.py's _is_crypto_ticker()
# is the single source of truth for crypto classification (backed by
# config.ASSET_CLASS). Importing it here means this script and
# compute_risk.py can't silently disagree on which tickers are crypto.
from scripts.compute_risk import _connect, _raise_if_locked, _is_crypto_ticker

# Any ticker whose most recent raw_prices row is older than this many
# days (relative to today) gets a staleness warning logged. This doesn't
# block forecasting — Prophet will still fit and forecast forward from
# whatever the last available date is — it's a signal that ingestion may
# be behind, which is worth knowing about rather than discovering later
# because a "30-day forecast" quietly started several days in the past.
STALENESS_WARNING_DAYS = 3

DEFAULT_CHANGEPOINT_PRIOR_SCALE = 0.05


def _changepoint_prior_scale_for(ticker: str) -> float:
    """Look up the asset-class-tuned changepoint_prior_scale for `ticker`.

    Falls back to Prophet's own default (with a warning) if the ticker is
    missing from config.ASSET_CLASS, or if its asset class is missing
    from config.CHANGEPOINT_PRIOR_SCALE_BY_ASSET_CLASS — both point to a
    config drift bug (e.g. a ticker added to TICKERS but not ASSET_CLASS)
    rather than something to fail the whole run over.
    """
    asset_class = ASSET_CLASS.get(ticker)
    if asset_class is None:
        print(f"run_forecasts: WARNING — '{ticker}' not found in config.ASSET_CLASS, "
              f"falling back to default changepoint_prior_scale={DEFAULT_CHANGEPOINT_PRIOR_SCALE}")
        return DEFAULT_CHANGEPOINT_PRIOR_SCALE

    scale = CHANGEPOINT_PRIOR_SCALE_BY_ASSET_CLASS.get(asset_class)
    if scale is None:
        print(f"run_forecasts: WARNING — asset class '{asset_class}' (ticker '{ticker}') not found "
              f"in config.CHANGEPOINT_PRIOR_SCALE_BY_ASSET_CLASS, falling back to "
              f"default changepoint_prior_scale={DEFAULT_CHANGEPOINT_PRIOR_SCALE}")
        return DEFAULT_CHANGEPOINT_PRIOR_SCALE

    return scale


def run_forecasts(db_path: str = DB_PATH, horizon: int = FORECAST_HORIZON_DAYS) -> None:
    """Read raw_prices, fit a per-ticker Prophet model, and write a
    `horizon`-day forward forecast to the forecasts table.

    Idempotent per run: rows for (ticker, forecast_date=today) are
    deleted and rewritten rather than appended, so rerunning on the same
    day doesn't duplicate rows. Rows from previous days' runs (different
    forecast_date) are left in place, since forecast_date is a distinct
    persisted column — the table is designed to hold multiple forecast
    vintages over time (needed to later compare an N-day-old forecast
    against what actually happened), not just the latest run.

    A single ticker's forecast failing (Prophet convergence issue,
    unexpectedly malformed data, etc.) is logged and skipped; it does not
    abort forecasting for the remaining tickers. This differs
    deliberately from compute_returns/compute_risk_scores in this same
    module family, which wrap the whole loop in one try/except — Prophet
    fits are failure-prone in a way simple arithmetic isn't, and the
    ticket calls for per-ticker error logging rather than an all-or-nothing run.
    """
    today_str = date.today().strftime("%Y-%m-%d")
    conn = _connect(db_path)
    try:
        conn.execute("BEGIN")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS forecasts (
                date TEXT NOT NULL,
                ticker TEXT NOT NULL,
                forecast_date TEXT NOT NULL,
                predicted_close REAL,
                lower_bound REAL,
                upper_bound REAL,
                PRIMARY KEY (date, ticker, forecast_date)
            )
        """)

        available_tickers = set(pd.read_sql("SELECT DISTINCT ticker FROM raw_prices", conn)["ticker"])
        missing = [t for t in TICKERS if t not in available_tickers]
        if missing:
            print(f"run_forecasts: WARNING — {len(missing)} configured ticker(s) "
                  f"not found in raw_prices, skipping: {missing}")

        succeeded, skipped, failed = [], [], []

        for ticker in TICKERS:
            if ticker not in available_tickers:
                continue

            prices_df = pd.read_sql(
                "SELECT date, close FROM raw_prices WHERE ticker = ? ORDER BY date",
                conn,
                params=(ticker,),
            )

            if len(prices_df) < MIN_ROWS_FOR_FORECAST:
                print(f"run_forecasts: WARNING — '{ticker}' has {len(prices_df)} rows, "
                      f"below MIN_ROWS_FOR_FORECAST={MIN_ROWS_FOR_FORECAST}, skipping")
                skipped.append(ticker)
                continue

            df = prices_df.rename(columns={"date": "ds", "close": "y"})
            df["ds"] = pd.to_datetime(df["ds"])

            last_training_date = df["ds"].max().date()
            staleness_days = (date.today() - last_training_date).days
            if staleness_days > STALENESS_WARNING_DAYS:
                print(f"run_forecasts: WARNING — '{ticker}' latest raw_prices row is "
                      f"{staleness_days} days old ({last_training_date}) — the forecast "
                      f"window will start from there, not from today. Check ingestion.")

            freq = "D" if _is_crypto_ticker(ticker) else "B"
            changepoint_prior_scale = _changepoint_prior_scale_for(ticker)

            try:
                forecast = fit_and_forecast(
                    df[["ds", "y"]],
                    horizon=horizon,
                    changepoint_prior_scale=changepoint_prior_scale,
                    freq=freq,
                    interval_width=PROPHET_INTERVAL_WIDTH,
                )
            except Exception as e:
                print(f"run_forecasts: ERROR — '{ticker}' failed to fit/forecast: {e}")
                failed.append(ticker)
                continue

            out = forecast.rename(columns={
                "ds": "date",
                "yhat": "predicted_close",
                "yhat_lower": "lower_bound",
                "yhat_upper": "upper_bound",
            }).copy()
            out["date"] = out["date"].dt.strftime("%Y-%m-%d")
            out["ticker"] = ticker
            out["forecast_date"] = today_str

            conn.execute(
                "DELETE FROM forecasts WHERE ticker = ? AND forecast_date = ?",
                (ticker, today_str),
            )
            out[["date", "ticker", "forecast_date", "predicted_close", "lower_bound", "upper_bound"]].to_sql(
                "forecasts", conn, if_exists="append", index=False
            )

            print(f"run_forecasts: '{ticker}' done — {len(out)} rows "
                  f"({freq=}, changepoint_prior_scale={changepoint_prior_scale}), "
                  f"{out['date'].min()} -> {out['date'].max()}")
            succeeded.append(ticker)

        conn.commit()

        print(f"\nrun_forecasts: {len(succeeded)} succeeded, {len(skipped)} skipped "
              f"(insufficient history), {len(failed)} failed")
        if failed:
            print(f"run_forecasts: WARNING — failed tickers: {failed}")

    except Exception as e:
        conn.rollback()
        _raise_if_locked(e, db_path)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    run_forecasts()