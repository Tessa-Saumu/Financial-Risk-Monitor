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

# Asset class per ticker. Used to (a) group tickers for the Prophet
# changepoint_prior_scale cross-validation grid in
# notebooks/03_prophet_tuning.ipynb, and (b) look up which tuned value to
# apply per ticker in scripts/run_forecasts.py. Kept as an explicit mapping
# rather than inferred from TICKERS' comment groupings above, since the
# comments are only human-readable and shouldn't be parsed as data.
ASSET_CLASS = {
    "AAPL": "equity", "MSFT": "equity", "GOOGL": "equity",
    "AMZN": "equity", "JPM": "equity",
    "SPY": "etf", "QQQ": "etf", "TLT": "etf", "GLD": "etf",
    "BTC-USD": "crypto", "ETH-USD": "crypto",
}

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

# Minimum rows of [ds, y] history required before a ticker is forecast.
# Distinct from MIN_ROWS_PER_TICKER below, which gates ingestion
# completeness (a full historical load from PRICE_START_DATE); 
MIN_ROWS_FOR_FORECAST = 200

# Width of the yhat_lower/yhat_upper uncertainty interval. Prophet's own
# default is 0.80; 
PROPHET_INTERVAL_WIDTH = 0.95

# changepoint_prior_scale controls how flexible Prophet's piecewise-linear
# trend is allowed to be at changepoints (Prophet's docs: default 0.05,
# tune on a log scale roughly over [0.001, 0.5], via cross-validation —
# treated as dataset-specific, not a universal constant). 
CHANGEPOINT_PRIOR_SCALE_BY_ASSET_CLASS = {
    "equity": 0.05,
    "etf": 0.05,
    "crypto": 0.05,
}

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