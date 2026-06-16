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
