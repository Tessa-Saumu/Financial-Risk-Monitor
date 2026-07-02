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

# Portfolio weights used by run_monte_carlo(). None -> equal-weight across
# whatever tickers actually have data in asset_returns at run time.
# To pin specific weights,  keys not present in
# asset_returns are ignored with a warning, remaining weights are
# renormalised to sum to 1.0.
PORTFOLIO_WEIGHTS = None

# Simulated path is flagged breach_flag=1 if final_value falls below
# initial_value * (1 - MONTE_CARLO_DRAWDOWN_THRESHOLD).
MONTE_CARLO_DRAWDOWN_THRESHOLD = 0.20

# Wall-clock ceiling (seconds) for a MONTE_CARLO_PATHS x FORECAST_HORIZON_DAYS
MONTE_CARLO_RUNTIME_BUDGET_SECONDS = 120

# ── Validation thresholds ─────────────────────────────────────
# Minimum rows expected per ticker for a full load from PRICE_START_DATE
MIN_ROWS_PER_TICKER = 1_000

# Minimum number of tickers that must succeed for the pipeline to continue
MIN_TICKERS_REQUIRED = 5

# Maximum allowed gap in days between consecutive macro observations
MAX_MACRO_GAP_DAYS = 35