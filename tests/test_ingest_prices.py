"""
test_ingest_prices.py — unit tests for ingest_prices.py.

All yfinance.download calls are mocked so the suite runs offline and
deterministically. Tests are organised around the four questions the spec
requires:
  1. Normal case        — data is downloaded and written correctly.
  2. HTTP / empty error — bad tickers are caught and logged without crashing.
  3. Upsert (re-run)    — a second run must not create duplicate rows.
  4. Abort gate         — RuntimeError when fewer than MIN_TICKERS_REQUIRED succeed.

The incremental-fetch test uses five distinct tickers (two pre-seeded, three
fresh) so every download call is a separate, independently assertable fetch
rather than the same ticker being skipped as already-up-to-date.
"""
import sqlite3
from datetime import date, timedelta
from unittest.mock import patch

import pandas as pd
import pytest

import config
from scripts.ingest_prices import (
    _fetch_window,
    _get_last_stored_date,
    _upsert_prices,
    _download_ticker,
    ingest_prices,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def db(tmp_path, monkeypatch):
    """
    Temporary SQLite DB with the raw_prices table.
    Patches sqlite3.connect so every call inside ingest_prices uses this DB file.
    """
    db_file = tmp_path / "test_database.db"
    
    # 1. Save the REAL function before we patch anything!
    real_connect = sqlite3.connect
    
    # 2. Use the real function to setup our test's connection
    conn = real_connect(db_file)
    conn.execute("""
        CREATE TABLE raw_prices (
            date    TEXT NOT NULL,
            ticker  TEXT NOT NULL,
            open    REAL,
            high    REAL,
            low     REAL,
            close   REAL,
            volume  INTEGER,
            PRIMARY KEY (date, ticker)
        )
    """)
    conn.commit()

    # 3. Patch ingest_prices to use the REAL function, but force our temp file path
    monkeypatch.setattr(
        "scripts.ingest_prices.sqlite3.connect", 
        lambda *a, **kw: real_connect(db_file)
    )

    yield conn

    # 4. Clean up
    conn.close()


def _make_df(n: int = 5, start: str = "2024-01-02") -> pd.DataFrame:
    """Synthetic OHLCV DataFrame that looks like yfinance output."""
    dates = pd.bdate_range(start=start, periods=n)
    df = pd.DataFrame(
        {
            "open":   [100.0 + i for i in range(n)],
            "high":   [105.0 + i for i in range(n)],
            "low":    [95.0 + i  for i in range(n)],
            "close":  [102.0 + i for i in range(n)],
            "volume": [1_000_000 + i * 1000 for i in range(n)],
        },
        index=dates,
    )
    df.index.name = "Date"
    return df


def _large_df() -> pd.DataFrame:
    """1 200-row DataFrame — clears the MIN_ROWS_PER_TICKER threshold."""
    return _make_df(n=1200, start="2020-01-02")


# ── _fetch_window ─────────────────────────────────────────────────────────────


class TestFetchWindow:
    def test_no_stored_data_uses_config_start(self):
        start, end = _fetch_window(None)
        assert start == config.PRICE_START_DATE
        assert end == (date.today() + timedelta(days=1)).isoformat()

    def test_incremental_starts_day_after_last(self):
        start, _ = _fetch_window("2024-06-01")
        assert start == "2024-06-02"

    def test_already_up_to_date_returns_empty_sentinels(self):
        today = date.today().isoformat()
        start, end = _fetch_window(today)
        assert start == "" and end == ""


# ── _get_last_stored_date ─────────────────────────────────────────────────────


class TestGetLastStoredDate:
    def test_returns_none_for_empty_table(self, db):
        assert _get_last_stored_date(db, "AAPL") is None

    def test_returns_most_recent_date(self, db):
        rows = [
            ("2024-01-02", "AAPL", 100, 105, 95, 102, 1_000_000),
            ("2024-01-05", "AAPL", 103, 108, 98, 105, 1_200_000),
            ("2024-01-03", "AAPL", 101, 106, 96, 103, 1_100_000),
        ]
        _upsert_prices(db, rows)
        assert _get_last_stored_date(db, "AAPL") == "2024-01-05"

    def test_is_ticker_specific(self, db):
        _upsert_prices(db, [("2024-01-02", "AAPL", 100, 105, 95, 102, 1_000_000)])
        _upsert_prices(db, [("2024-06-01", "MSFT", 200, 205, 195, 202, 2_000_000)])
        assert _get_last_stored_date(db, "AAPL") == "2024-01-02"
        assert _get_last_stored_date(db, "MSFT") == "2024-06-01"


# ── _upsert_prices ────────────────────────────────────────────────────────────


class TestUpsertPrices:
    def test_inserts_new_rows(self, db):
        rows = [
            ("2024-01-02", "AAPL", 100, 105, 95, 102, 1_000_000),
            ("2024-01-03", "AAPL", 102, 107, 97, 104, 1_100_000),
        ]
        assert _upsert_prices(db, rows) == 2
        assert db.execute("SELECT COUNT(*) FROM raw_prices").fetchone()[0] == 2

    def test_rerun_does_not_duplicate_rows(self, db):
        row = [("2024-01-02", "AAPL", 100, 105, 95, 102, 1_000_000)]
        _upsert_prices(db, row)
        _upsert_prices(db, row)
        assert db.execute("SELECT COUNT(*) FROM raw_prices").fetchone()[0] == 1

    def test_upsert_replaces_values_on_conflict(self, db):
        _upsert_prices(db, [("2024-01-02", "AAPL", 100, 105, 95, 102, 1_000_000)])
        _upsert_prices(db, [("2024-01-02", "AAPL", 200, 205, 195, 202, 2_000_000)])
        close = db.execute(
            "SELECT close FROM raw_prices WHERE date='2024-01-02' AND ticker='AAPL'"
        ).fetchone()[0]
        assert close == 202.0

    def test_multiple_tickers_stored_independently(self, db):
        rows = [
            ("2024-01-02", "AAPL", 100, 105, 95, 102, 1_000_000),
            ("2024-01-02", "MSFT", 200, 205, 195, 202, 2_000_000),
        ]
        _upsert_prices(db, rows)
        assert db.execute("SELECT COUNT(*) FROM raw_prices").fetchone()[0] == 2


# ── _download_ticker ──────────────────────────────────────────────────────────


class TestDownloadTicker:
    @patch("scripts.ingest_prices.yf.download")
    def test_returns_dataframe_for_valid_ticker(self, mock_dl):
        mock_dl.return_value = _make_df()
        result = _download_ticker("AAPL", "2024-01-02", "2024-01-08")
        assert result is not None and not result.empty

    @patch("scripts.ingest_prices.yf.download")
    def test_returns_none_for_empty_dataframe(self, mock_dl):
        """yfinance silent-drop: empty DF must be treated as failure, not crash."""
        mock_dl.return_value = pd.DataFrame()
        assert _download_ticker("INVALID", "2024-01-02", "2024-01-08") is None

    @patch("scripts.ingest_prices.yf.download")
    def test_returns_none_on_network_exception(self, mock_dl):
        mock_dl.side_effect = ConnectionError("Network unreachable")
        assert _download_ticker("AAPL", "2024-01-02", "2024-01-08") is None

    @patch("scripts.ingest_prices.yf.download")
    def test_returns_none_for_missing_required_columns(self, mock_dl):
        mock_dl.return_value = pd.DataFrame({"random": [1, 2, 3]})
        assert _download_ticker("AAPL", "2024-01-02", "2024-01-08") is None


# ── ingest_prices (full function) ─────────────────────────────────────────────


class TestIngestPrices:
    @patch("scripts.ingest_prices.yf.download")
    def test_normal_case_populates_db(self, mock_dl, db):
        mock_dl.return_value = _large_df()
        ingest_prices()
        count = db.execute("SELECT COUNT(DISTINCT ticker) FROM raw_prices").fetchone()[0]
        assert count == len(config.TICKERS)

    @patch("scripts.ingest_prices.yf.download")
    def test_incremental_run_requests_delta_only(self, mock_dl, db):
        """
        Each ticker with existing data must fetch from last_stored + 1 day;
        tickers with no data must fetch from PRICE_START_DATE.

        Uses five distinct tickers so every download call is a separate,
        meaningful assertion — not the same ticker being skipped as up-to-date.
        """
        tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "JPM"]

        # Seed two tickers with different last-stored dates; leave the rest empty.
        _upsert_prices(db, [("2024-06-01", "AAPL", 100, 105, 95, 102, 1_000_000)])
        _upsert_prices(db, [("2024-03-15", "MSFT", 200, 205, 195, 202, 2_000_000)])

        mock_dl.return_value = _make_df(n=3, start="2024-06-03")

        with patch("scripts.ingest_prices.TICKERS", tickers):
            ingest_prices()

        # Build a map of ticker → start arg used in each download call.
        call_map = {c[1]["tickers"]: c[1]["start"] for c in mock_dl.call_args_list}

        assert call_map["AAPL"] == "2024-06-02",  "AAPL: should fetch from day after last stored"
        assert call_map["MSFT"] == "2024-03-16",  "MSFT: should fetch from day after last stored"
        assert call_map["GOOGL"] == config.PRICE_START_DATE, "GOOGL: no history, should use config start"
        assert call_map["AMZN"] == config.PRICE_START_DATE,  "AMZN: no history, should use config start"
        assert call_map["JPM"] == config.PRICE_START_DATE,   "JPM: no history, should use config start"

    @patch("scripts.ingest_prices.yf.download")
    def test_rerun_does_not_create_duplicate_rows(self, mock_dl, db):
        mock_dl.return_value = _large_df()
        ingest_prices()
        first = db.execute("SELECT COUNT(*) FROM raw_prices").fetchone()[0]

        ingest_prices()
        second = db.execute("SELECT COUNT(*) FROM raw_prices").fetchone()[0]

        assert second == first, f"Row count grew from {first} to {second} on re-run"

    @patch("scripts.ingest_prices.yf.download")
    def test_failed_ticker_counted_but_others_succeed(self, mock_dl, db):
        """A bad ticker must not stop good ones from being written."""
        def side_effect(tickers, **kwargs):
            return pd.DataFrame() if tickers == "INVALID" else _large_df()

        mock_dl.side_effect = side_effect
        tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "JPM", "INVALID"]

        with patch("scripts.ingest_prices.TICKERS", tickers):
            ingest_prices()

        bad_count = db.execute(
            "SELECT COUNT(*) FROM raw_prices WHERE ticker='INVALID'"
        ).fetchone()[0]
        good_count = db.execute(
            "SELECT COUNT(DISTINCT ticker) FROM raw_prices WHERE ticker != 'INVALID'"
        ).fetchone()[0]
        assert bad_count == 0
        assert good_count == 5

    @patch("scripts.ingest_prices.yf.download")
    def test_abort_gate_raises_when_too_few_succeed(self, mock_dl, db):
        """Fewer than MIN_TICKERS_REQUIRED must raise RuntimeError."""
        mock_dl.return_value = pd.DataFrame()
        few_tickers = ["FAKE1", "FAKE2", "FAKE3"]  # fewer than MIN_TICKERS_REQUIRED

        with patch("scripts.ingest_prices.TICKERS", few_tickers):
            with pytest.raises(RuntimeError, match="minimum"):
                ingest_prices()

    @patch("scripts.ingest_prices.yf.download")
    def test_http_error_case_counts_as_failure(self, mock_dl, db):
        """An exception from yfinance is treated as a failed ticker."""
        mock_dl.side_effect = Exception("SSL handshake failed")
        few_tickers = ["FAKE1", "FAKE2", "FAKE3"]

        with patch("scripts.ingest_prices.TICKERS", few_tickers):
            with pytest.raises(RuntimeError):
                ingest_prices()