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
