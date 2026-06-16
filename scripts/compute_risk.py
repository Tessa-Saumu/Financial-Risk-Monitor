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
