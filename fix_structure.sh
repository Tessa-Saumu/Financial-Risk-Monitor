#!/bin/bash
# ─────────────────────────────────────────────────────────────
# Financial Risk Monitor — Project Structure Creation Script
# Run from the project root directory (where README.md lives)
# ─────────────────────────────────────────────────────────────
set -e
echo "📈 Scaffolding Financial Risk Monitor project structure..."

# ── 1. Create top-level directories ──────────────────────────
mkdir -p scripts
mkdir -p data/raw
mkdir -p data/processed
mkdir -p database
mkdir -p models/prophet
mkdir -p models/monte_carlo
mkdir -p dashboard
mkdir -p notebooks
mkdir -p tests
mkdir -p docs
mkdir -p assets

# ── 2. Remove any stray getkeep files ────────────────────────
find . -name "getkeep" -delete

# ── 3. Create ingestion scripts ───────────────────────────────
cat > scripts/ingest_prices.py << 'PY'
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
PY

cat > scripts/ingest_macro.py << 'PY'
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
PY

cat > scripts/compute_risk.py << 'PY'
"""
compute_risk.py — reads raw_prices and raw_macro from SQLite and computes:
  - daily_return, rolling_7d_vol, rolling_30d_vol, drawdown → asset_returns table
  - var_95, cvar_95, volatility_score, drawdown_score, combined_risk_score → risk_scores table

Usage:
    python scripts/compute_risk.py
"""
import sqlite3
import pandas as pd
import numpy as np
from config import DB_PATH


def compute_returns(db_path: str = DB_PATH) -> None:
    # TODO: compute daily returns and rolling volatility per ticker
    raise NotImplementedError


def compute_risk_scores(db_path: str = DB_PATH) -> None:
    # TODO: compute VaR 95%, CVaR, and combined_risk_score (0-1) per ticker per day
    raise NotImplementedError


def run_monte_carlo(db_path: str = DB_PATH, n_paths: int = 10_000) -> None:
    # TODO: simulate 10,000 portfolio paths from current date
    # TODO: compute final value distribution, VaR, CVaR, breach probability
    # TODO: write results to monte_carlo table
    raise NotImplementedError


if __name__ == "__main__":
    compute_returns()
    compute_risk_scores()
    run_monte_carlo()
PY

cat > scripts/run_forecasts.py << 'PY'
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
PY

cat > scripts/init_db.py << 'PY'
"""
init_db.py — creates the SQLite database and all six tables if they
do not already exist. Safe to re-run (uses CREATE TABLE IF NOT EXISTS).

Tables created:
  raw_prices, raw_macro, asset_returns,
  risk_scores, forecasts, monte_carlo

Usage:
    python scripts/init_db.py
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
    forecast_date     TEXT NOT NULL,
    ticker            TEXT NOT NULL,
    target_date       TEXT NOT NULL,
    predicted_close   REAL,
    lower_bound       REAL,
    upper_bound       REAL,
    PRIMARY KEY (forecast_date, ticker, target_date)
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
    print(f"✅ Database initialised at {db_path}")


if __name__ == "__main__":
    init_db()
PY

# ── 4. Create config.py ───────────────────────────────────────
cat > config.py << 'PY'
"""
config.py — central configuration for the Financial Risk Monitor pipeline.
Edit this file to change tickers, FRED series, date ranges, or file paths.
"""
from pathlib import Path

# ── File paths ────────────────────────────────────────────────
DB_PATH = str(Path(__file__).parent / "database" / "financial_risk.db")

# ── Asset universe ────────────────────────────────────────────
TICKERS = [
    # Equities
    "AAPL", "MSFT", "GOOGL", "AMZN", "JPM",
    # ETFs
    "SPY", "QQQ", "TLT", "GLD",
    # Crypto
    "BTC-USD", "ETH-USD",
]

# ── FRED macro series ─────────────────────────────────────────
FRED_SERIES = [
    "FEDFUNDS",   # Federal Funds Rate
    "CPIAUCSL",   # CPI (inflation)
    "UNRATE",     # Unemployment Rate
    "DGS10",      # 10-Year Treasury Yield
    "VIXCLS",     # CBOE Volatility Index
]

# ── Date range ────────────────────────────────────────────────
PRICE_START_DATE = "2020-01-01"

# ── Forecasting ───────────────────────────────────────────────
FORECAST_HORIZON_DAYS = 30

# ── Monte Carlo ───────────────────────────────────────────────
MONTE_CARLO_PATHS = 10_000
PY

# ── 5. Create models stubs ────────────────────────────────────
cat > models/__init__.py << 'PY'
# Financial Risk Monitor — ML models package
PY

cat > models/prophet/__init__.py << 'PY'
# Prophet forecasting helpers
PY

cat > models/prophet/forecast.py << 'PY'
"""
forecast.py — helper functions for fitting Prophet models and
generating forward-looking price forecasts with confidence intervals.
Called by scripts/run_forecasts.py.
"""
import pandas as pd
from prophet import Prophet


def fit_and_forecast(df: pd.DataFrame, horizon: int = 30) -> pd.DataFrame:
    """
    Fit a Prophet model on a single asset's price history
    and return a forecast DataFrame with ds, yhat, yhat_lower, yhat_upper.

    Args:
        df: DataFrame with columns ['ds', 'y'] (date and close price)
        horizon: number of days to forecast forward
    """
    # TODO: fit Prophet, call make_future_dataframe, return forecast
    raise NotImplementedError
PY

cat > models/monte_carlo/__init__.py << 'PY'
# Monte Carlo simulation helpers
PY

cat > models/monte_carlo/simulation.py << 'PY'
"""
simulation.py — Monte Carlo portfolio simulation using historical
return distributions.

Simulates n_paths portfolio trajectories forward from the current date.
Computes final value distribution, VaR 95%, CVaR 95%, and breach probability.
Called by scripts/compute_risk.py.
"""
import numpy as np
import pandas as pd


def simulate(
    returns_df: pd.DataFrame,
    weights: dict,
    n_paths: int = 10_000,
    horizon: int = 30,
    initial_value: float = 100_000.0,
) -> pd.DataFrame:
    """
    Run Monte Carlo simulation.

    Args:
        returns_df: DataFrame of daily returns per ticker
        weights: dict of {ticker: portfolio_weight}
        n_paths: number of simulation paths
        horizon: number of trading days to simulate forward
        initial_value: starting portfolio value

    Returns:
        DataFrame with columns: run_id, date, portfolio_value, final_value, breach_flag
    """
    # TODO: sample from historical return distribution, simulate paths
    raise NotImplementedError
PY

cat > models/risk_metrics.py << 'PY'
"""
risk_metrics.py — core financial risk metric calculations.

Functions:
    daily_returns(prices) → Series
    rolling_volatility(returns, window) → Series
    max_drawdown(prices) → Series (running drawdown)
    value_at_risk(returns, confidence=0.95) → float
    conditional_var(returns, confidence=0.95) → float
    combined_risk_score(vol_score, drawdown_score, var_score) → float (0–1)
"""
import numpy as np
import pandas as pd


def daily_returns(prices: pd.Series) -> pd.Series:
    return prices.pct_change().dropna()


def rolling_volatility(returns: pd.Series, window: int) -> pd.Series:
    return returns.rolling(window).std() * np.sqrt(252)


def max_drawdown(prices: pd.Series) -> pd.Series:
    peak = prices.cummax()
    return (prices - peak) / peak


def value_at_risk(returns: pd.Series, confidence: float = 0.95) -> float:
    # TODO: compute historical VaR at given confidence level
    raise NotImplementedError


def conditional_var(returns: pd.Series, confidence: float = 0.95) -> float:
    # TODO: compute CVaR (Expected Shortfall) beyond VaR threshold
    raise NotImplementedError


def combined_risk_score(*component_scores: float) -> float:
    # TODO: normalise and combine component scores to a single 0–1 signal
    raise NotImplementedError
PY

# ── 6. Create notebooks ───────────────────────────────────────
touch notebooks/01_data_exploration.ipynb
touch notebooks/02_risk_metrics_dev.ipynb
touch notebooks/03_prophet_tuning.ipynb
touch notebooks/04_monte_carlo_analysis.ipynb
touch notebooks/05_dashboard_data_validation.ipynb

# ── 7. Create test stubs ──────────────────────────────────────
cat > tests/__init__.py << 'PY'
PY

touch tests/test_ingest_prices.py
touch tests/test_ingest_macro.py
touch tests/test_risk_metrics.py
touch tests/test_prophet_forecast.py
touch tests/test_monte_carlo.py

# ── 8. Docs placeholders ──────────────────────────────────────
touch docs/schema_diagram.md
touch docs/data_refresh_workflow.md
touch docs/fred_api_setup.md

# ── 9. Create .env.example ────────────────────────────────────
cat > .env.example << 'ENV'
# Copy this file to .env and add your FRED API key
# Get a free key at: https://fred.stlouisfed.org/docs/api/api_key.html
FRED_API_KEY=your_fred_api_key_here
ENV

# ── 10. Create requirements.txt ───────────────────────────────
cat > requirements.txt << 'REQS'
# Data ingestion
yfinance
requests

# Data processing
pandas
numpy
openpyxl

# Forecasting
prophet

# Risk modelling
scipy

# Database
# sqlite3 is part of Python stdlib — no install needed

# Notebooks
jupyter
ipykernel

# Utilities
python-dotenv
rich
REQS

# ── 11. Create .gitignore ─────────────────────────────────────
cat > .gitignore << 'IGNORE'
# Python
__pycache__/
*.pyc
*.pyo
*.pyd
*.egg-info/
dist/
build/
.venv/
venv/
env/

# Environment
.env

# Jupyter
.ipynb_checkpoints/
*.ipynb_checkpoints

# OS
.DS_Store
Thumbs.db

# Database (large binary — exclude from git)
database/*.db

# Power BI (binary — optionally exclude)
# dashboard/*.pbix
IGNORE

# ── 12. Add .gitkeep to all empty leaf dirs ───────────────────
find . -type d \
  ! -path "./.git/*" \
  ! -name ".git" \
  -exec sh -c '
    if [ -z "$(ls -A "$1")" ]; then
      touch "$1/.gitkeep"
      echo "  + .gitkeep → $1"
    fi
  ' _ {} \;

echo ""
echo "✅ Done! Financial Risk Monitor structure created:"
echo ""
tree -a --dirsfirst -I '.git' 2>/dev/null || find . ! -path './.git/*' | sort