"""
compute_risk.py — reads raw_prices and raw_macro from SQLite and computes:
  - daily_return, rolling_7d_vol, rolling_30d_vol, drawdown → asset_returns table
  - var_95, cvar_95, volatility_score, drawdown_score, combined_risk_score → risk_scores table

Price column used throughout: `close`. The price that carries forward into the next
day's comparison, and every downstream metric (vol, drawdown, VaR) is
built on the resulting return series.

Usage:
    python -m scripts.compute_risk 
"""
import sqlite3

import numpy as np
import pandas as pd

from config import DB_PATH, TICKERS, MIN_TICKERS_REQUIRED
from models.risk_metrics import (
    daily_returns,
    rolling_volatility,
    max_drawdown,
    value_at_risk,
    conditional_var,
    combined_risk_score,
)

# ── Local pipeline constants ──────────────────────────────────────────────

# Trailing window (in periods) used for rolling VaR / CVaR calculation.
# 252 ≈ one trading year for equities/ETFs.
VAR_LOOKBACK_WINDOW = 252

# Minimum number of return observations required before VaR/CVaR are
# computed for a ticker/day. Below this, historical quantile estimates
# are too noisy to be meaningful.
MIN_VAR_OBSERVATIONS = 30


def _is_crypto_ticker(ticker: str) -> bool:
    """Identify 24/7-market tickers using the yfinance '-USD' suffix
    convention (matches config.TICKERS: BTC-USD, ETH-USD, etc).

    This is a naming-convention check, not a hardcoded list, so it
    self-extends if more crypto tickers are added to config.TICKERS later
    without needing a second place to update.
    
    Flag if tickers like spot gold/silver XAU-USD are added in future 
    implementations this logic must be revisited.
    """
    return ticker.upper().endswith("-USD")


def _periods_per_year(ticker: str) -> int:
    """Annualisation factor for rolling_volatility: 365 for crypto, 
    252 for equities/ETFs.
    """
    return 365 if _is_crypto_ticker(ticker) else 252


def _min_max_normalize(series: pd.Series) -> pd.Series:
    """Normalise a series to [0, 1] against its own min/max.

    This is what combined_risk_score's docstring refers to as
    "normalise against its own historical range" — done here, per
    ticker, before any value is passed into combined_risk_score, which
    only ever receives already-normalised [0, 1] inputs.

    If every value in the series is identical (max == min), there's no
    meaningful range to normalise against; we return 0.5 (neutral) for
    every point rather than dividing by zero.
    """
    lo, hi = series.min(), series.max()
    if pd.isna(lo) or pd.isna(hi) or hi == lo:
        return pd.Series(0.5, index=series.index)
    return (series - lo) / (hi - lo)


def _connect(db_path: str) -> sqlite3.Connection:
    """Open a SQLite connection with a longer lock-wait timeout.

    SQLite allows only one writer at a time. The default Python sqlite3
    timeout is 5 seconds; we extend it to 30s so a short-lived lock (e.g.
    another process mid-write) has a real chance to clear before we give
    up. If it's still locked after 30s, _raise_if_locked (called from
    each function's except block) turns the raw error into something
    that actually explains what to do.
    """
    return sqlite3.connect(db_path, timeout=30)


def _raise_if_locked(exc: Exception, db_path: str) -> None:
    """If `exc` is a SQLite/pandas 'database is locked' error, re-raise it
    with an explanation of the likely cause and how to fix it.

    A lock can surface on ANY statement inside a transaction — not just
    the initial connect() — since SQLite defers acquiring the write lock
    until it's actually needed. pandas.read_sql also wraps the underlying
    sqlite3.OperationalError in its own DatabaseError, so we check the
    message text rather than the exception type to catch both.
    """
    if "locked" in str(exc).lower():
        raise sqlite3.OperationalError(
            f"Could not write to '{db_path}' — the database is locked. "
            "This usually means another program has it open (DB Browser "
            "for SQLite, a Jupyter notebook, a VS Code SQLite viewer, "
            "etc.). Close that connection and rerun. If nothing obvious "
            "is open, check for a leftover .db-journal or -wal file next "
            "to the database, which can indicate a previous run didn't "
            "shut down cleanly."
        ) from exc


def compute_returns(db_path: str = DB_PATH) -> None:
    """Read raw_prices, compute per-ticker return/vol/drawdown metrics,
    and write the results to asset_returns.

    Idempotent: re-running this deletes and rewrites each ticker's rows
    rather than appending duplicates, so it's safe to call repeatedly as
    part of a refresh workflow.
    """
    conn = _connect(db_path)
    try:
        conn.execute("BEGIN")
        available_tickers = set(pd.read_sql("SELECT DISTINCT ticker FROM raw_prices", conn)["ticker"])
        missing = [t for t in TICKERS if t not in available_tickers]
        if missing:
            print(f"compute_returns: WARNING — {len(missing)} configured ticker(s) "
                  f"not found in raw_prices, skipping: {missing}")

        succeeded = 0

        conn.execute("""
            CREATE TABLE IF NOT EXISTS asset_returns (
                date TEXT NOT NULL,
                ticker TEXT NOT NULL,
                daily_return REAL,
                rolling_7d_vol REAL,
                rolling_30d_vol REAL,
                drawdown REAL,
                PRIMARY KEY (date, ticker)
            )
        """)

        for ticker in TICKERS:
            if ticker not in available_tickers:
                continue

            prices_df = pd.read_sql(
                "SELECT date, close FROM raw_prices WHERE ticker = ? ORDER BY date",
                conn,
                params=(ticker,),
            )
            if prices_df.empty:
                continue

            prices_df["date"] = pd.to_datetime(prices_df["date"])
            close = prices_df.set_index("date")["close"]
            ppy = _periods_per_year(ticker)

            returns = daily_returns(close)
            vol_7d = rolling_volatility(returns, window=7, periods_per_year=ppy)
            vol_30d = rolling_volatility(returns, window=30, periods_per_year=ppy)
            drawdown = max_drawdown(close)

            # daily_returns drops the first row (no prior price), so its
            # index is one shorter than `close`/`drawdown`. Reindex
            # everything to the returns index — the first day of a
            # ticker's history has no daily_return by definition and is
            # correctly excluded, matching the acceptance criterion that
            # only the rolling-window warm-up period contains NaNs.
            out = pd.DataFrame({
                "daily_return": returns,
                "rolling_7d_vol": vol_7d,
                "rolling_30d_vol": vol_30d,
                "drawdown": drawdown.reindex(returns.index),
            })
            out = out.reset_index().rename(columns={"index": "date"})
            out["ticker"] = ticker
            out["date"] = out["date"].dt.strftime("%Y-%m-%d")

            conn.execute("DELETE FROM asset_returns WHERE ticker = ?", (ticker,))
            out[["date", "ticker", "daily_return", "rolling_7d_vol", "rolling_30d_vol", "drawdown"]].to_sql(
                "asset_returns", conn, if_exists="append", index=False
            )
            succeeded += 1

        conn.commit()

        if succeeded < MIN_TICKERS_REQUIRED:
            print(f"compute_returns: WARNING — only {succeeded}/{len(TICKERS)} configured "
                  f"tickers were processed, below MIN_TICKERS_REQUIRED={MIN_TICKERS_REQUIRED}. "
                  "Downstream risk_scores and dashboard coverage will be incomplete.")
    except Exception as e:
        conn.rollback()
        _raise_if_locked(e, db_path)
        raise
    finally:
        conn.close()


def compute_risk_scores(db_path: str = DB_PATH) -> None:
    """Read asset_returns, compute VaR/CVaR and component risk scores per
    ticker per day, and write the results to risk_scores.

    VaR/CVaR at each date are computed using a trailing lookback window
    (VAR_LOOKBACK_WINDOW, default 252 periods ≈ 1 trading year) of
    daily_return history up to and including that date — a rolling
    historical-simulation VaR, not a single value for the whole series.
    Days with fewer than MIN_VAR_OBSERVATIONS of history are skipped
    (left as NaN) since a handful of observations makes the quantile
    estimate unreliable.

    Component scores (volatility_score, drawdown_score, and VaR-/CVaR-
    derived scores) are each min-max normalised against that ticker's
    own historical range before being combined. Because you can't
    meaningfully min-max a single day's volatility, drawdown, VaR and
    CVaR against another metric, since they're different units and scales.

    Iterates config.TICKERS, so a ticker that failed upstream
    in compute_returns is skipped with a warning.
    """
    conn = _connect(db_path)
    try:
        conn.execute("BEGIN")
        available_tickers = set(pd.read_sql("SELECT DISTINCT ticker FROM asset_returns", conn)["ticker"])
        missing = [t for t in TICKERS if t not in available_tickers]
        if missing:
            print(f"compute_risk_scores: WARNING — {len(missing)} configured ticker(s) "
                  f"not found in asset_returns, skipping: {missing}")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS risk_scores (
                date TEXT NOT NULL,
                ticker TEXT NOT NULL,
                var_95 REAL,
                cvar_95 REAL,
                volatility_score REAL,
                drawdown_score REAL,
                combined_risk_score REAL,
                PRIMARY KEY (date, ticker)
            )
        """)

        for ticker in TICKERS:
            if ticker not in available_tickers:
                continue

            df = pd.read_sql(
                "SELECT date, daily_return, rolling_30d_vol, drawdown "
                "FROM asset_returns WHERE ticker = ? ORDER BY date",
                conn,
                params=(ticker,),
            )
            if df.empty:
                continue

            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")

            var_95 = pd.Series(index=df.index, dtype=float)
            cvar_95 = pd.Series(index=df.index, dtype=float)

            returns = df["daily_return"].dropna()
            for current_date in df.index:
                # Trailing window of returns strictly up to current_date.
                window_returns = returns.loc[:current_date].tail(VAR_LOOKBACK_WINDOW)
                if len(window_returns) < MIN_VAR_OBSERVATIONS:
                    continue
                var_95.loc[current_date] = value_at_risk(window_returns, confidence=0.95)
                cvar_95.loc[current_date] = conditional_var(window_returns, confidence=0.95)

            df["var_95"] = var_95
            df["cvar_95"] = cvar_95

            # Normalise each component against this ticker's own history.
            # VaR/CVaR are typically negative (losses), so we normalise
            # their absolute magnitude: a bigger loss -> a bigger score.
            vol_score = _min_max_normalize(df["rolling_30d_vol"])
            drawdown_score = _min_max_normalize(df["drawdown"].abs())
            var_score = _min_max_normalize(df["var_95"].abs())
            cvar_score = _min_max_normalize(df["cvar_95"].abs())

            combined = pd.Series(index=df.index, dtype=float)
            for idx in df.index:
                components = [vol_score.loc[idx], drawdown_score.loc[idx],
                              var_score.loc[idx], cvar_score.loc[idx]]
                if any(pd.isna(c) for c in components):
                    continue
                combined.loc[idx] = combined_risk_score(*components)

            out = pd.DataFrame({
                "var_95": df["var_95"],
                "cvar_95": df["cvar_95"],
                "volatility_score": vol_score,
                "drawdown_score": drawdown_score,
                "combined_risk_score": combined,
            })
            out = out.reset_index().rename(columns={"index": "date"})
            out["ticker"] = ticker
            out["date"] = out["date"].dt.strftime("%Y-%m-%d")

            conn.execute("DELETE FROM risk_scores WHERE ticker = ?", (ticker,))
            out[["date", "ticker", "var_95", "cvar_95", "volatility_score",
                 "drawdown_score", "combined_risk_score"]].to_sql(
                "risk_scores", conn, if_exists="append", index=False
            )

        conn.commit()
    except Exception as e:
        conn.rollback()
        _raise_if_locked(e, db_path)
        raise
    finally:
        conn.close()


def run_monte_carlo(db_path: str = DB_PATH, n_paths: int = 10_000) -> None:
    # Out of scope for this issue: the task checklist covers compute_returns
    # and compute_risk_scores only. Monte Carlo portfolio simulation is a
    # separate, larger piece of work (portfolio-level, not per-ticker) that
    # belongs in its own issue/milestone.
    raise NotImplementedError(
        "run_monte_carlo is out of scope for Issue 3 (Risk Modelling) "
        "Monte Carlo simulation will be handled in following Issue 4 (Implement Monte Carlo simulation)."
    )

if __name__ == "__main__":
    print("compute_risk.py — starting risk computation pipeline")
 
    print("\n[1/2] Computing returns, volatility, and drawdown...")
    compute_returns()
    print("      ✓ asset_returns populated")
 
    print("\n[2/2] Computing VaR, CVaR, and combined risk scores...")
    compute_risk_scores()
    print("      ✓ risk_scores populated")
 
    print("\nPipeline completed successfully.")
    print("Note: run_monte_carlo() is not yet implemented (Issue 4, Phase 3 "
          "milestone) and is intentionally not called here. Calling it "
          "directly will raise NotImplementedError until that issue lands.")