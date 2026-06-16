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
