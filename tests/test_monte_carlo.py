"""
tests/test_monte_carlo.py — unit tests for models/monte_carlo/simulation.py

Covers the Phase 3 acceptance criteria:
  - output row count == n_paths * horizon
  - breach_flag is always 0 or 1
  - zero-volatility synthetic return series -> all paths identical
  - 10,000 paths x 30 days completes in under 2 minutes on a single CPU
Plus a couple of extras for production-grade coverage: weight
renormalisation, single-ticker portfolios, and missing-ticker validation.
"""
import numpy as np
import pandas as pd
import pytest

from config import MONTE_CARLO_RUNTIME_BUDGET_SECONDS
from models.monte_carlo.simulation import simulate


# ── Fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def synthetic_returns_df():
    """Two tickers, 500 trading days, mildly-positive-drift random returns.
    Enough history to bootstrap from without being slow to build.
    """
    rng = np.random.default_rng(42)
    dates = pd.bdate_range("2023-01-01", periods=500)
    return pd.DataFrame(
        {
            "AAPL": rng.normal(0.0006, 0.018, size=len(dates)),
            "MSFT": rng.normal(0.0005, 0.016, size=len(dates)),
        },
        index=dates,
    )


@pytest.fixture
def zero_vol_returns_df():
    """Constant daily return, no variance at all. Every bootstrap draw
    pulls the identical value, so every path must compound identically.
    """
    dates = pd.bdate_range("2023-01-01", periods=300)
    return pd.DataFrame({"AAPL": np.full(len(dates), 0.0005)}, index=dates)


# ── Shape / output contract ───────────────────────────────────────────

def test_output_row_count_equals_paths_times_horizon(synthetic_returns_df):
    n_paths, horizon = 200, 15
    result = simulate(
        synthetic_returns_df,
        weights={"AAPL": 0.6, "MSFT": 0.4},
        n_paths=n_paths,
        horizon=horizon,
        random_seed=1,
    )
    assert len(result) == n_paths * horizon


def test_output_has_expected_columns(synthetic_returns_df):
    result = simulate(
        synthetic_returns_df,
        weights={"AAPL": 1.0},
        n_paths=50,
        horizon=10,
        random_seed=1,
    )
    assert list(result.columns) == ["run_id", "date", "portfolio_value", "final_value", "breach_flag"]
    assert result["run_id"].nunique() == 50


# ── breach_flag correctness ───────────────────────────────────────────

def test_breach_flag_is_always_zero_or_one(synthetic_returns_df):
    result = simulate(
        synthetic_returns_df,
        weights={"AAPL": 0.6, "MSFT": 0.4},
        n_paths=500,
        horizon=30,
        random_seed=2,
    )
    assert set(result["breach_flag"].unique()).issubset({0, 1})


def test_breach_flag_matches_threshold_logic(synthetic_returns_df):
    initial_value = 100_000.0
    threshold = 0.20
    result = simulate(
        synthetic_returns_df,
        weights={"AAPL": 0.6, "MSFT": 0.4},
        n_paths=500,
        horizon=30,
        initial_value=initial_value,
        drawdown_threshold=threshold,
        random_seed=3,
    )
    per_path = result.drop_duplicates(subset="run_id")
    expected = (per_path["final_value"] < initial_value * (1 - threshold)).astype(int)
    assert (per_path["breach_flag"].values == expected.values).all()


# ── Zero-volatility edge case ──────────────────────────────────────────

def test_zero_volatility_all_paths_identical(zero_vol_returns_df):
    result = simulate(
        zero_vol_returns_df,
        weights={"AAPL": 1.0},
        n_paths=100,
        horizon=20,
        random_seed=4,
    )
    # Every path must trace the exact same trajectory, since every
    # bootstrap draw pulls the same constant daily return regardless of
    # which of the (identical) historical days gets sampled.
    final_values = result.drop_duplicates(subset="run_id")["final_value"]
    assert np.allclose(final_values, final_values.iloc[0])

    # Same check day-by-day, not just at the endpoint.
    pivoted = result.pivot(index="date", columns="run_id", values="portfolio_value")
    for date, row in pivoted.iterrows():
        assert np.allclose(row.values, row.values[0]), f"paths diverged on {date}"

    # And breach_flag should be uniform too — either every path breaches
    # or none do, since they're all identical.
    assert result["breach_flag"].nunique() == 1


# ── Runtime budget ─────────────────────────────────────────────────────

def test_runtime_under_budget_for_full_scale_run(synthetic_returns_df):
    import time

    start = time.perf_counter()
    simulate(
        synthetic_returns_df,
        weights={"AAPL": 0.6, "MSFT": 0.4},
        n_paths=10_000,
        horizon=30,
        random_seed=5,
    )
    elapsed = time.perf_counter() - start
    assert elapsed < MONTE_CARLO_RUNTIME_BUDGET_SECONDS, (
        f"10,000-path x 30-day simulation took {elapsed:.1f}s, "
        f"exceeding the {MONTE_CARLO_RUNTIME_BUDGET_SECONDS}s budget"
    )


# ── Input validation / production-grade extras ─────────────────────────

def test_weights_not_summing_to_one_are_renormalised(synthetic_returns_df, capsys):
    # 0.3 + 0.3 = 0.6, not 1.0 -> should renormalise to 0.5/0.5 and warn,
    # not silently under-weight the portfolio.
    result = simulate(
        synthetic_returns_df,
        weights={"AAPL": 0.3, "MSFT": 0.3},
        n_paths=50,
        horizon=10,
        random_seed=6,
    )
    captured = capsys.readouterr()
    assert "renormalising" in captured.out
    assert len(result) == 50 * 10


def test_single_ticker_portfolio_reduces_to_that_tickers_returns(synthetic_returns_df):
    # weight=1.0 on one ticker should behave like bootstrapping directly
    # from that ticker's own return series — sanity check that the
    # weighted-sum collapse doesn't do anything strange for the trivial case.
    result = simulate(
        synthetic_returns_df,
        weights={"AAPL": 1.0},
        n_paths=1000,
        horizon=30,
        random_seed=7,
    )
    per_path_returns = result.drop_duplicates(subset="run_id")["final_value"] / 100_000.0 - 1.0
    # Simulated 30-day outcomes should stay within a broad, sane band
    # given AAPL's ~1.8% daily vol in the fixture — this just guards
    # against a gross unit error (e.g. forgetting to compound correctly).
    assert per_path_returns.between(-0.9, 5.0).all()


def test_missing_ticker_in_weights_raises(synthetic_returns_df):
    with pytest.raises(ValueError, match="not present in returns_df"):
        simulate(
            synthetic_returns_df,
            weights={"AAPL": 0.5, "TSLA": 0.5},
            n_paths=10,
            horizon=5,
        )


def test_empty_returns_df_raises():
    with pytest.raises(ValueError, match="empty"):
        simulate(pd.DataFrame(), weights={"AAPL": 1.0}, n_paths=10, horizon=5)