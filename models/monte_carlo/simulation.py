"""
simulation.py — Monte Carlo portfolio simulation using historical
return distributions.

Simulates n_paths portfolio trajectories forward from the current date.
Computes final value distribution, VaR 95%, CVaR 95%, and breach probability.
Called by scripts/compute_risk.py.

Method: historical (bootstrap) simulation, not parametric. The portfolio's
own historical daily-return series (weighted sum of its constituent
tickers' returns) is treated as the empirical return distribution, and
each simulated day is drawn with replacement from that series. This
preserves the real fat-tailed, non-normal shape of historical returns
instead of assuming a bell curve.
"""
import time

import numpy as np
import pandas as pd


def _weighted_portfolio_returns(returns_df: pd.DataFrame, weights: dict) -> pd.Series:
    """Collapse a wide per-ticker return DataFrame into a single weighted
    portfolio daily-return series.

    returns_df: date-indexed, one column per ticker (daily returns).
    weights: {ticker: weight}, must sum to ~1.0 (validated by caller).

    A date is only included if ALL weighted tickers have an observed
    return that day — a day with a missing ticker is dropped rather than
    treated as a 0% return for that ticker, since silently zero-filling
    would understate the portfolio's true historical volatility on days
    data simply wasn't available (e.g. one ticker started trading later).
    """
    tickers = list(weights.keys())
    missing_cols = [t for t in tickers if t not in returns_df.columns]
    if missing_cols:
        raise ValueError(
            f"weights reference ticker(s) not present in returns_df: {missing_cols}"
        )

    aligned = returns_df[tickers].dropna(how="any")
    if aligned.empty:
        raise ValueError(
            "No overlapping dates with complete return data across all "
            f"weighted tickers {tickers}. Cannot build a portfolio return "
            "series."
        )

    weight_vector = pd.Series(weights)
    portfolio_returns = aligned.mul(weight_vector, axis=1).sum(axis=1)
    return portfolio_returns


def simulate(
    returns_df: pd.DataFrame,
    weights: dict,
    n_paths: int = 10_000,
    horizon: int = 30,
    initial_value: float = 100_000.0,
    drawdown_threshold: float = 0.20,
    random_seed: int | None = None,
) -> pd.DataFrame:
    """
    Run Monte Carlo simulation.

    Args:
        returns_df: DataFrame of daily returns per ticker, date-indexed
            (wide format: one column per ticker). Callers reading from a
            long-format SQL table should pivot first — see
            scripts/compute_risk.py:run_monte_carlo().
        weights: dict of {ticker: portfolio_weight}. Must reference columns
            present in returns_df. Renormalised to sum to 1.0 if not
            already (with a warning), rather than silently misweighting.
        n_paths: number of simulation paths.
        horizon: number of trading days to simulate forward.
        initial_value: starting portfolio value.
        drawdown_threshold: fraction of initial_value that defines a
            breach if final_value falls below
            initial_value * (1 - drawdown_threshold). Default 0.20 (20% loss).
        random_seed: optional seed for reproducibility (tests use this;
            production runs should leave it None for a fresh draw).

    Returns:
        Long-format DataFrame with columns: run_id, date, portfolio_value,
        final_value, breach_flag. One row per (path, day) — n_paths *
        horizon rows total. `date` starts today and runs `horizon` trading
        days forward, shared across all paths (this is a forward-looking
        simulation from "now", not a backtest against real calendar dates).
        `final_value` and `breach_flag` are repeated on every row of a
        given run_id for convenience (so a consumer can filter this table
        alone without a separate join to get either the full trajectory
        or just the endpoint).
    """
    if returns_df.empty:
        raise ValueError("returns_df is empty — nothing to sample from.")
    if not weights:
        raise ValueError("weights is empty — no tickers to build a portfolio from.")
    if n_paths <= 0 or horizon <= 0:
        raise ValueError(f"n_paths and horizon must be positive, got {n_paths=}, {horizon=}")

    weight_sum = sum(weights.values())
    if weight_sum <= 0:
        raise ValueError(f"weights must sum to a positive number, got {weight_sum}")
    if not np.isclose(weight_sum, 1.0, atol=1e-6):
        print(f"simulate: WARNING — weights sum to {weight_sum:.6f}, renormalising to 1.0")
        weights = {k: v / weight_sum for k, v in weights.items()}

    start = time.perf_counter()

    portfolio_returns = _weighted_portfolio_returns(returns_df, weights)
    if len(portfolio_returns) < 2:
        raise ValueError(
            f"Only {len(portfolio_returns)} overlapping historical return "
            "observation(s) available — too few to bootstrap from."
        )

    rng = np.random.default_rng(random_seed)

    # Vectorized draw: n_paths x horizon samples, with replacement, from
    # the empirical portfolio return distribution. One call instead of a
    # per-path Python loop — this is what keeps 10,000 x 30 comfortably
    # under the 2-minute budget (a Python-level loop over paths would not).
    sampled_returns = rng.choice(
        portfolio_returns.values, size=(n_paths, horizon), replace=True
    )

    # Cumulative compounding per path: value[t] = initial_value * prod(1+r) up to t.
    growth_factors = np.cumprod(1.0 + sampled_returns, axis=1)
    portfolio_values = initial_value * growth_factors  # shape (n_paths, horizon)

    final_values = portfolio_values[:, -1]
    breach_threshold = initial_value * (1.0 - drawdown_threshold)
    breach_flags = (final_values < breach_threshold).astype(int)

    dates = pd.bdate_range(start=pd.Timestamp.now().normalize(), periods=horizon)

    run_ids = np.repeat(np.arange(n_paths), horizon)
    date_col = np.tile(dates, n_paths)
    value_col = portfolio_values.reshape(-1)
    final_value_col = np.repeat(final_values, horizon)
    breach_col = np.repeat(breach_flags, horizon)

    result = pd.DataFrame({
        "run_id": run_ids,
        "date": date_col,
        "portfolio_value": value_col,
        "final_value": final_value_col,
        "breach_flag": breach_col,
    })

    elapsed = time.perf_counter() - start
    print(
        f"simulate: {n_paths:,} paths x {horizon}d horizon completed in "
        f"{elapsed:.2f}s (sampled from {len(portfolio_returns):,} historical "
        f"portfolio-return observations across {len(weights)} tickers)"
    )

    return result