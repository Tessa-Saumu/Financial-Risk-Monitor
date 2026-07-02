"""
risk_metrics.py — core financial risk metric calculations.

All functions here are pure: no database calls, no I/O, no side effects.
They accept pandas Series (and plain floats) and return pandas Series or
floats.

Functions:
    daily_returns(prices) → Series
    rolling_volatility(returns, window) → Series
    max_drawdown(prices) → Series (running drawdown)
    value_at_risk(returns, confidence=0.95) → float
    conditional_var(returns, confidence=0.95) → float
    combined_risk_score(*scores, weights=None) → float (0–1)
"""
import numpy as np
import pandas as pd


def daily_returns(prices: pd.Series) -> pd.Series:
    """Percentage change from one period to the next.

    The first element of pct_change() is always NaN
    """
    return prices.pct_change().dropna()


def rolling_volatility(returns: pd.Series, window: int, periods_per_year: int = 252) -> pd.Series:
    """Annualised rolling volatility (standard deviation of returns).

    Uses a trailing window of `window` periods and annualises by
    multiplying by sqrt(periods_per_year).

    `periods_per_year` defaults to 252, the standard number of trading
    days/year for equities and ETFs on a normal market calendar. It is
    NOT correct for every asset class like crypto trades. 
    The caller (see scripts/compute_risk.py) is responsible for passing
    the right value per ticker.
    """
    return returns.rolling(window).std() * np.sqrt(periods_per_year)


def max_drawdown(prices: pd.Series) -> pd.Series:
    """Running drawdown from the cumulative peak, at every point in time.

    This is always <= 0: it's 0 at a new all-time high, and increasingly
    negative the further the current price has fallen from its most
    recent peak.
    """
    peak = prices.cummax()
    return (prices - peak) / peak


def value_at_risk(returns: pd.Series, confidence: float = 0.95) -> float:
    """Historical-simulation Value at Risk.

    Sorts the empirical return distribution and returns the
    (1 - confidence) quantile — e.g. at 95% confidence, the 5th
    percentile return.

    Sign convention: this returns the RAW quantile, not an absolute
    loss magnitude. For a typical return distribution (mean near zero,
    some negative days) this comes out negative, e.g. -0.032 meaning
    "on the worst ~5% of days, you lost 3.2% or more." If the input
    distribution happens to be entirely non-negative
    """
    if len(returns) == 0:
        raise ValueError("value_at_risk: returns series is empty")
    return float(returns.quantile(1 - confidence))


def conditional_var(returns: pd.Series, confidence: float = 0.95) -> float:
    """Conditional Value at Risk / Expected Shortfall.

    The mean of all returns at or beyond the VaR threshold, 
    CVaR is always <= VaR for the same return series and 
    confidence level.
    """
    if len(returns) == 0:
        raise ValueError("conditional_var: returns series is empty")

    var = value_at_risk(returns, confidence)
    tail = returns[returns <= var]

    if len(tail) == 0:
        # Degenerate case: with very few data points, no observation may
        # fall at or below the quantile itself. Fall back to the VaR
        # value so CVaR stays defined and the CVaR <= VaR invariant holds.
        return var

    return float(tail.mean())


def combined_risk_score(*component_scores: float, weights: "list[float] | None" = None) -> float:
    """Combine pre-normalised [0, 1] component risk scores into one signal.

    Min-max normalisation only makes sense against a distribution (e.g.
    a ticker's own volatility over its trailing history)
    So the contract here is: every value in `component_scores` is
    already a [0, 1] number (produced by the caller normalising each
    metric against its own historical rang, this function's
    only job is to combine them.


    Weighting rationale:
    Default is equal weighting (1/n per component). This is the
    defensible default when there's no empirical basis yet for
    believing one risk dimension (volatility vs. drawdown vs. tail
    risk) dominates portfolio outcomes for a given asset and it keeps
    the function agnostic to how many components are passed in. 
    Pass `weights` explicitly (same length as component_scores,
    summing to 1) to override 

    Raises:
        ValueError if no scores are given, if any score is outside
        [0, 1], or if `weights` doesn't match the number of scores or
        doesn't sum to 1 (within floating-point tolerance).
    """
    if len(component_scores) == 0:
        raise ValueError("combined_risk_score: at least one score is required")

    for s in component_scores:
        if not (0.0 <= s <= 1.0):
            raise ValueError(
                f"combined_risk_score: all component scores must be in [0, 1], got {s}. "
                "Normalise each metric against its own historical range before combining."
            )

    if weights is None:
        weights = [1.0 / len(component_scores)] * len(component_scores)
    else:
        if len(weights) != len(component_scores):
            raise ValueError(
                f"combined_risk_score: got {len(component_scores)} scores but "
                f"{len(weights)} weights — they must match."
            )
        if not np.isclose(sum(weights), 1.0):
            raise ValueError(f"combined_risk_score: weights must sum to 1, got {sum(weights)}")

    score = sum(s * w for s, w in zip(component_scores, weights))
    # Clamp for floating-point safety only — inputs are already validated to
    # [0, 1] and weights sum to 1, so this should be a no-op in practice.
    return float(np.clip(score, 0.0, 1.0))