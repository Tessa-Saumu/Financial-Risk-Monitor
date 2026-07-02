"""
test_risk_metrics.py — known-value unit tests for models/risk_metrics.py

Run with:
    pytest tests/test_risk_metrics.py -v
"""
import numpy as np
import pandas as pd
import pytest

from models.risk_metrics import (
    daily_returns,
    rolling_volatility,
    max_drawdown,
    value_at_risk,
    conditional_var,
    combined_risk_score,
)


# ---------------------------------------------------------------------------
# daily_returns
# ---------------------------------------------------------------------------

def test_daily_returns_known_values():
    prices = pd.Series([100.0, 110.0, 99.0])
    returns = daily_returns(prices)
    # 100 -> 110 is +10%, 110 -> 99 is -10%
    assert returns.iloc[0] == pytest.approx(0.10)
    assert returns.iloc[1] == pytest.approx(-0.10)


def test_daily_returns_drops_first_nan():
    prices = pd.Series([100.0, 105.0, 110.0])
    returns = daily_returns(prices)
    # pct_change() produces a leading NaN; daily_returns must drop it,
    # not just leave it in the series.
    assert len(returns) == len(prices) - 1
    assert not returns.isna().any()


# ---------------------------------------------------------------------------
# rolling_volatility
# ---------------------------------------------------------------------------

def test_rolling_volatility_constant_returns_is_near_zero():
    # A perfectly constant return series has zero variance -> zero vol,
    # even after annualising.
    returns = pd.Series([0.01] * 10)
    vol = rolling_volatility(returns, window=5)
    assert vol.iloc[-1] == pytest.approx(0.0, abs=1e-9)


def test_rolling_volatility_annualisation_factor():
    # Hand-computed: std of [0.01, -0.01, 0.01, -0.01, 0.01] with ddof=1,
    # then multiplied by sqrt(252) (the default periods_per_year), should
    # match manual calculation.
    values = [0.01, -0.01, 0.01, -0.01, 0.01]
    returns = pd.Series(values)
    vol = rolling_volatility(returns, window=5)
    expected = np.std(values, ddof=1) * np.sqrt(252)
    assert vol.iloc[-1] == pytest.approx(expected)


def test_rolling_volatility_custom_periods_per_year():
    # A 24/7 market (e.g. crypto) trades 365 days/year, not 252 -- callers
    # need to be able to override the annualisation factor, and the result
    # must actually differ from the 252-day default.
    values = [0.01, -0.01, 0.01, -0.01, 0.01]
    returns = pd.Series(values)
    vol_365 = rolling_volatility(returns, window=5, periods_per_year=365)
    vol_252 = rolling_volatility(returns, window=5, periods_per_year=252)
    expected_365 = np.std(values, ddof=1) * np.sqrt(365)
    assert vol_365.iloc[-1] == pytest.approx(expected_365)
    assert vol_365.iloc[-1] > vol_252.iloc[-1]


def test_rolling_volatility_warmup_period_is_nan():
    returns = pd.Series([0.01, 0.02, -0.01, 0.03, 0.00])
    vol = rolling_volatility(returns, window=3)
    # First (window - 1) = 2 values can't have a full window yet.
    assert vol.iloc[:2].isna().all()
    assert not pd.isna(vol.iloc[2])


# ---------------------------------------------------------------------------
# max_drawdown
# ---------------------------------------------------------------------------

def test_drawdown_monotonically_increasing_is_always_zero():
    prices = pd.Series([100.0, 105.0, 110.0, 120.0, 150.0])
    dd = max_drawdown(prices)
    assert (dd == 0).all()


def test_drawdown_known_dip():
    # Peak at 100 (idx 0), drops to 80 (idx 1) -> drawdown = (80-100)/100 = -0.20
    # Then recovers to 90 (idx 2), peak is still 100 -> drawdown = (90-100)/100 = -0.10
    # Then new peak 110 (idx 3) -> drawdown = 0
    prices = pd.Series([100.0, 80.0, 90.0, 110.0])
    dd = max_drawdown(prices)
    assert dd.iloc[0] == pytest.approx(0.0)
    assert dd.iloc[1] == pytest.approx(-0.20)
    assert dd.iloc[2] == pytest.approx(-0.10)
    assert dd.iloc[3] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# value_at_risk
# ---------------------------------------------------------------------------

def test_var_flat_positive_series():
    # NOTE: the original issue text says VaR on a flat +1% series should be
    # "~-1%". Under the raw-quantile sign convention (confirmed for this
    # implementation), that's not correct: if EVERY return in the series is
    # exactly +0.01, the 5th percentile of the distribution is also +0.01 --
    # there is no loss anywhere in the data for VaR to report. VaR only
    # comes out negative when the distribution actually contains a lower
    # tail of negative returns. This test asserts the mathematically
    # correct behaviour rather than the issue's shorthand description.
    returns = pd.Series([0.01] * 100)
    var = value_at_risk(returns, confidence=0.95)
    assert var == pytest.approx(0.01)


def test_var_with_realistic_loss_tail():
    # 90 days at +1%, 10 days at -8% -> a full 10% loss tail (comfortably
    # past the 5% cutoff, avoiding quantile-interpolation edge effects
    # right at the boundary) so the 5th percentile unambiguously lands in
    # the loss tail, giving a negative VaR.
    returns = pd.Series([0.01] * 90 + [-0.08] * 10)
    var = value_at_risk(returns, confidence=0.95)
    assert var < 0


def test_var_empty_series_raises():
    with pytest.raises(ValueError):
        value_at_risk(pd.Series([], dtype=float))


# ---------------------------------------------------------------------------
# conditional_var
# ---------------------------------------------------------------------------

def test_cvar_le_var_on_skewed_distribution():
    returns = pd.Series([0.01] * 90 + [-0.05] * 5 + [-0.15] * 5)
    var = value_at_risk(returns, confidence=0.95)
    cvar = conditional_var(returns, confidence=0.95)
    # CVaR averages further into the tail than the VaR cutoff, so it must
    # be at least as negative (numerically <=) as VaR.
    assert cvar <= var


def test_cvar_matches_manual_tail_mean():
    returns = pd.Series([0.01] * 90 + [-0.05] * 5 + [-0.15] * 5)
    var = value_at_risk(returns, confidence=0.95)
    expected_tail_mean = returns[returns <= var].mean()
    assert conditional_var(returns, confidence=0.95) == pytest.approx(expected_tail_mean)


def test_cvar_empty_series_raises():
    with pytest.raises(ValueError):
        conditional_var(pd.Series([], dtype=float))


# ---------------------------------------------------------------------------
# combined_risk_score
# ---------------------------------------------------------------------------

def test_combined_risk_score_in_bounds():
    for _ in range(20):
        scores = list(np.random.uniform(0, 1, size=4))
        result = combined_risk_score(*scores)
        assert 0.0 <= result <= 1.0


def test_combined_risk_score_equal_weight_average():
    # With default equal weighting, the result is just the mean.
    result = combined_risk_score(0.2, 0.4, 0.6, 0.8)
    assert result == pytest.approx(0.5)


def test_combined_risk_score_custom_weights():
    # Weight the first score fully; result should equal that score.
    result = combined_risk_score(0.9, 0.1, weights=[1.0, 0.0])
    assert result == pytest.approx(0.9)


def test_combined_risk_score_rejects_out_of_range_input():
    with pytest.raises(ValueError):
        combined_risk_score(0.5, 1.2)
    with pytest.raises(ValueError):
        combined_risk_score(-0.1, 0.5)


def test_combined_risk_score_rejects_bad_weights():
    with pytest.raises(ValueError):
        combined_risk_score(0.5, 0.5, weights=[0.5])  # wrong length
    with pytest.raises(ValueError):
        combined_risk_score(0.5, 0.5, weights=[0.3, 0.3])  # doesn't sum to 1


def test_combined_risk_score_requires_at_least_one_score():
    with pytest.raises(ValueError):
        combined_risk_score()