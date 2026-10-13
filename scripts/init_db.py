"""
init_db.py — creates the SQLite database and all six tables if they
do not already exist. Safe to re-run (uses CREATE TABLE IF NOT EXISTS).

Tables created:
  raw_prices, raw_macro, asset_returns,
  risk_scores, forecasts, monte_carlo

Usage:
    python -m scripts.init_db   
"""
import sqlite3
from config import DB_PATH


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS raw_prices (
    date         TEXT NOT NULL,
    ticker       TEXT NOT NULL,
    open         REAL,
    high         REAL,
    low          REAL,
    close        REAL,
    volume       INTEGER,
    PRIMARY KEY (date, ticker)
);

CREATE TABLE IF NOT EXISTS raw_macro (
    date             TEXT NOT NULL,
    indicator_name   TEXT NOT NULL,
    indicator_value  REAL,
    PRIMARY KEY (date, indicator_name)
);

CREATE TABLE IF NOT EXISTS asset_returns (
    date             TEXT NOT NULL,
    ticker           TEXT NOT NULL,
    daily_return     REAL,
    rolling_7d_vol   REAL,
    rolling_30d_vol  REAL,
    drawdown         REAL,
    PRIMARY KEY (date, ticker)
);

CREATE TABLE IF NOT EXISTS risk_scores (
    date                  TEXT NOT NULL,
    ticker                TEXT NOT NULL,
    var_95                REAL,
    cvar_95               REAL,
    volatility_score      REAL,
    drawdown_score        REAL,
    combined_risk_score   REAL,
    PRIMARY KEY (date, ticker)
);

CREATE TABLE IF NOT EXISTS forecasts (
    date              TEXT NOT NULL,  -- Changed from target_date to match README
    ticker            TEXT NOT NULL,
    forecast_date     TEXT NOT NULL,
    predicted_close   REAL,
    lower_bound       REAL,
    upper_bound       REAL,
    PRIMARY KEY (date, ticker, forecast_date) -- Updated PK to match
);

CREATE TABLE IF NOT EXISTS monte_carlo (
    run_id           INTEGER NOT NULL,
    date             TEXT NOT NULL,
    portfolio_value  REAL,
    final_value      REAL,
    breach_flag      INTEGER,
    PRIMARY KEY (run_id, date)
);
"""


def init_db(db_path: str = DB_PATH) -> None:
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()
    print(f"Database initialised at {db_path}")


if __name__ == "__main__":
    init_db()
