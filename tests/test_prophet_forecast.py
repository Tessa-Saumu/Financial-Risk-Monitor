"""
test_prophet_forecast.py — tests for models/prophet/forecast.py and
scripts/run_forecasts.py.

Two layers, matching the ticket's split:
  1. Unit tests on fit_and_forecast() directly, against synthetic data —
     fast, no DB, no I/O.
  2. A pipeline test that seeds a temp SQLite DB with raw_prices and runs
     run_forecasts() against it for real, then checks what landed in
     the forecasts table.
"""
import sqlite3
from datetime import date

import numpy as np
import pandas as pd
import pytest

from models.prophet.forecast import fit_and_forecast
from scripts import run_forecasts as run_forecasts_module
from scripts.run_forecasts import run_forecasts

HORIZON = 30


# ── Synthetic data helpers ──────────────────────────────────────────────

def _synthetic_business_day_series(n=500, start_price=150.0, seed=1):
    """~2 years of weekday-only price history (mimics an equity/ETF)."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize() - pd.Timedelta(days=1), periods=n)
    y = start_price + np.cumsum(rng.normal(0.05, 1.5, n))
    return pd.DataFrame({"ds": dates, "y": y})


def _synthetic_calendar_day_series(n=500, start_price=40000.0, seed=2):
    """~500 days of every-calendar-day price history (mimics crypto)."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range(end=pd.Timestamp.today().normalize() - pd.Timedelta(days=1), periods=n)
    y = start_price + np.cumsum(rng.normal(5, 400, n))
    return pd.DataFrame({"ds": dates, "y": y})


# ── Layer 1: fit_and_forecast unit tests ────────────────────────────────

@pytest.fixture(scope="module")
def equity_forecast():
    df = _synthetic_business_day_series()
    return fit_and_forecast(df, horizon=HORIZON, changepoint_prior_scale=0.05, freq="B", interval_width=0.95)


@pytest.fixture(scope="module")
def crypto_forecast():
    df = _synthetic_calendar_day_series()
    return fit_and_forecast(df, horizon=HORIZON, changepoint_prior_scale=0.05, freq="D", interval_width=0.95)


class TestFitAndForecastRowCount:
    """Acceptance criterion: exactly `horizon` rows, for every ticker,
    regardless of freq — periods=horizon in make_future_dataframe
    guarantees this independent of calendar vs business-day spacing."""

    def test_equity_exactly_horizon_rows(self, equity_forecast):
        assert len(equity_forecast) == HORIZON

    def test_crypto_exactly_horizon_rows(self, crypto_forecast):
        assert len(crypto_forecast) == HORIZON

    def test_output_excludes_training_history(self, equity_forecast):
        # include_history=False: every row should be a genuinely future
        # date relative to when the synthetic training data ended.
        cutoff = pd.Timestamp.today().normalize() - pd.Timedelta(days=1)
        assert (equity_forecast["ds"] > cutoff).all()


class TestFitAndForecastValidity:

    @pytest.mark.parametrize("forecast_fixture", ["equity_forecast", "crypto_forecast"])
    def test_no_nan_values(self, forecast_fixture, request):
        fc = request.getfixturevalue(forecast_fixture)
        assert not fc[["yhat", "yhat_lower", "yhat_upper"]].isna().any().any()

    @pytest.mark.parametrize("forecast_fixture", ["equity_forecast", "crypto_forecast"])
    def test_bounds_ordering_holds_for_every_row(self, forecast_fixture, request):
        fc = request.getfixturevalue(forecast_fixture)
        assert (fc["yhat_lower"] <= fc["yhat"]).all()
        assert (fc["yhat"] <= fc["yhat_upper"]).all()


class TestFitAndForecastInputValidation:

    def test_missing_column_raises(self):
        df = pd.DataFrame({"ds": pd.date_range("2024-01-01", periods=10), "price": range(10)})
        with pytest.raises(ValueError, match="missing required column"):
            fit_and_forecast(df, horizon=5)

    def test_nan_in_y_raises(self):
        df = _synthetic_business_day_series(n=250)
        df.loc[5, "y"] = np.nan
        with pytest.raises(ValueError, match="NaN"):
            fit_and_forecast(df, horizon=5, freq="B")

    def test_custom_horizon_respected(self):
        df = _synthetic_calendar_day_series(n=250)
        fc = fit_and_forecast(df, horizon=7, freq="D")
        assert len(fc) == 7


# ── Layer 2: run_forecasts() pipeline test, against a real temp DB ─────

@pytest.fixture
def seeded_db(tmp_path, monkeypatch):
    """A temp SQLite DB with raw_prices for one healthy equity-like
    ticker, one healthy crypto-like ticker, and one thin ticker that
    should be skipped — mirrors the AAPL/BTC-USD/MSFT smoke test used
    during development.
    """
    db_path = str(tmp_path / "test_financial_risk.db")
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE raw_prices (
            date TEXT NOT NULL, ticker TEXT NOT NULL,
            open REAL, high REAL, low REAL, close REAL, volume INTEGER
        )
    """)

    rows = []
    equity_df = _synthetic_business_day_series(n=600, seed=10)
    for d, c in zip(equity_df["ds"], equity_df["y"]):
        rows.append((d.strftime("%Y-%m-%d"), "TEST_EQUITY", c, c, c, c, 1_000_000))

    crypto_df = _synthetic_calendar_day_series(n=600, seed=11)
    for d, c in zip(crypto_df["ds"], crypto_df["y"]):
        rows.append((d.strftime("%Y-%m-%d"), "TEST_CRYPTO-USD", c, c, c, c, 1_000))

    thin_df = _synthetic_business_day_series(n=50, seed=12)
    for d, c in zip(thin_df["ds"], thin_df["y"]):
        rows.append((d.strftime("%Y-%m-%d"), "TEST_THIN", c, c, c, c, 500_000))

    conn.executemany("INSERT INTO raw_prices VALUES (?,?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()

    # Point the already-imported run_forecasts module at our test
    # universe and DB rather than the real config.TICKERS/DB_PATH —
    # patching the names bound inside run_forecasts_module, since that's
    # what the function body actually reads from.
    monkeypatch.setattr(run_forecasts_module, "TICKERS", ["TEST_EQUITY", "TEST_CRYPTO-USD", "TEST_THIN"])
    monkeypatch.setattr(run_forecasts_module, "ASSET_CLASS", {
        "TEST_EQUITY": "equity", "TEST_CRYPTO-USD": "crypto", "TEST_THIN": "equity",
    })
    monkeypatch.setattr(run_forecasts_module, "CHANGEPOINT_PRIOR_SCALE_BY_ASSET_CLASS", {
        "equity": 0.05, "etf": 0.05, "crypto": 0.05,
    })

    return db_path


class TestRunForecastsPipeline:

    def test_forecast_date_is_today_for_all_rows(self, seeded_db):
        run_forecasts(db_path=seeded_db)
        conn = sqlite3.connect(seeded_db)
        df = pd.read_sql("SELECT * FROM forecasts", conn)
        conn.close()

        today_str = date.today().strftime("%Y-%m-%d")
        assert not df.empty
        assert (df["forecast_date"] == today_str).all()

    def test_exactly_horizon_rows_per_forecasted_ticker(self, seeded_db):
        run_forecasts(db_path=seeded_db)
        conn = sqlite3.connect(seeded_db)
        df = pd.read_sql("SELECT * FROM forecasts", conn)
        conn.close()

        counts = df.groupby("ticker").size()
        assert counts["TEST_EQUITY"] == HORIZON
        assert counts["TEST_CRYPTO-USD"] == HORIZON

    def test_thin_ticker_is_skipped_not_written(self, seeded_db):
        run_forecasts(db_path=seeded_db)
        conn = sqlite3.connect(seeded_db)
        df = pd.read_sql("SELECT * FROM forecasts", conn)
        conn.close()

        assert "TEST_THIN" not in df["ticker"].values

    def test_no_nan_and_bounds_hold_in_written_table(self, seeded_db):
        run_forecasts(db_path=seeded_db)
        conn = sqlite3.connect(seeded_db)
        df = pd.read_sql("SELECT * FROM forecasts", conn)
        conn.close()

        assert not df[["predicted_close", "lower_bound", "upper_bound"]].isna().any().any()
        assert (df["lower_bound"] <= df["predicted_close"]).all()
        assert (df["predicted_close"] <= df["upper_bound"]).all()

    def test_rerun_same_day_is_idempotent(self, seeded_db):
        run_forecasts(db_path=seeded_db)
        conn = sqlite3.connect(seeded_db)
        first_count = pd.read_sql("SELECT COUNT(*) AS n FROM forecasts", conn)["n"][0]
        conn.close()

        run_forecasts(db_path=seeded_db)  # rerun same day
        conn = sqlite3.connect(seeded_db)
        second_count = pd.read_sql("SELECT COUNT(*) AS n FROM forecasts", conn)["n"][0]
        conn.close()

        assert second_count == first_count