"""
test_ingest_macro.py — unit tests for ingest_macro.py.

All requests.get calls are mocked so the suite runs offline and
deterministically without a real FRED_API_KEY. Tests are organised around
the four questions the spec requires:
  1. Normal case         — observations are fetched, parsed, and written.
  2. HTTP error cases    — 400 bad series, 401 bad key, 5xx server errors.
  3. Upsert (re-run)     — a second run must not create duplicate rows.
  4. Response parsing    — "." values dropped, non-numeric values dropped.

Additionally covers:
  - Gap detection (_check_gaps)
  - Missing API key (fail fast before any HTTP call)
  - Abort gate (RuntimeError when any series fails)

Why mock?
---------
Unit tests must be deterministic. By controlling what requests.get returns
we verify OUR logic — gap SQL, upsert, error routing — without depending on
FRED's API being up or a real key being present in CI.
"""
import sqlite3
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest
import requests

import config
from scripts.ingest_macro import (
    _check_gaps,
    _fetch_observations,
    _fetch_window,
    _get_last_stored_date,
    _require_api_key,
    _upsert_macro,
    ingest_macro,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def fake_api_key(monkeypatch):
    """Ensure FRED_API_KEY is always present in the test environment."""
    monkeypatch.setenv("FRED_API_KEY", "test_fake_key")


@pytest.fixture()
def db(monkeypatch):
    """
    In-memory SQLite DB with the raw_macro table (column name: indicator_value,
    matching init_db.py). Patches sqlite3.connect inside ingest_macro.
    """
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE raw_macro (
            date             TEXT NOT NULL,
            indicator_name   TEXT NOT NULL,
            indicator_value  REAL,
            PRIMARY KEY (date, indicator_name)
        )
    """)
    conn.commit()
    monkeypatch.setattr("ingest_macro.sqlite3.connect", lambda *a, **kw: conn)
    yield conn
    conn.close()


def _fred_response(observations: list[dict], status_code: int = 200) -> MagicMock:
    """Build a mock requests.Response for a FRED observations call."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = {"observations": observations}
    return mock


def _obs(date_str: str, value: str) -> dict:
    """Shorthand for a FRED observation dict (value is a string, as FRED sends it)."""
    return {"date": date_str, "realtime_start": date_str, "realtime_end": date_str, "value": value}


def _monthly(start: str = "2020-01-01", n: int = 12) -> list[dict]:
    """n monthly observations starting from start with plausible values."""
    from datetime import datetime
    base = datetime.strptime(start, "%Y-%m-%d")
    result = []
    for i in range(n):
        month_offset = (base.month - 1 + i)
        year = base.year + month_offset // 12
        month = month_offset % 12 + 1
        d = base.replace(year=year, month=month).strftime("%Y-%m-%d")
        result.append(_obs(d, str(3.5 + i * 0.1)))
    return result


# ── _require_api_key ──────────────────────────────────────────────────────────


class TestRequireApiKey:
    def test_raises_when_key_not_set(self, monkeypatch):
        monkeypatch.delenv("FRED_API_KEY", raising=False)
        with pytest.raises(EnvironmentError, match="FRED_API_KEY"):
            _require_api_key()

    def test_raises_on_whitespace_only_value(self, monkeypatch):
        monkeypatch.setenv("FRED_API_KEY", "   ")
        with pytest.raises(EnvironmentError, match="FRED_API_KEY"):
            _require_api_key()

    def test_returns_key_when_present(self, monkeypatch):
        monkeypatch.setenv("FRED_API_KEY", "my_real_key")
        assert _require_api_key() == "my_real_key"


# ── _fetch_window ─────────────────────────────────────────────────────────────


class TestFetchWindow:
    def test_no_stored_data_uses_config_start(self):
        start, end = _fetch_window(None)
        assert start == config.PRICE_START_DATE
        assert end == date.today().isoformat()

    def test_incremental_starts_day_after_last(self):
        start, _ = _fetch_window("2024-06-01")
        assert start == "2024-06-02"

    def test_already_up_to_date_returns_sentinels(self):
        today = date.today().isoformat()
        start, end = _fetch_window(today)
        assert start == "" and end == ""


# ── _fetch_observations ───────────────────────────────────────────────────────


class TestFetchObservations:
    @patch("ingest_macro.requests.get")
    def test_normal_case_parses_values_as_float(self, mock_get):
        mock_get.return_value = _fred_response([_obs("2024-01-01", "5.33"), _obs("2024-02-01", "5.25")])
        result = _fetch_observations("FEDFUNDS", "key", "2024-01-01", "2024-02-01")
        assert len(result) == 2
        assert result[0] == {"date": "2024-01-01", "value": 5.33}
        assert isinstance(result[0]["value"], float)

    @patch("ingest_macro.requests.get")
    def test_drops_missing_dot_values(self, mock_get):
        """FRED uses '.' for unpublished data — these must be silently dropped."""
        mock_get.return_value = _fred_response([
            _obs("2024-01-01", "5.33"),
            _obs("2024-02-01", "."),
            _obs("2024-03-01", "5.10"),
        ])
        result = _fetch_observations("FEDFUNDS", "key", "2024-01-01", "2024-03-01")
        assert len(result) == 2
        assert all(r["date"] != "2024-02-01" for r in result)

    @patch("ingest_macro.requests.get")
    def test_drops_non_numeric_values(self, mock_get):
        """Non-numeric strings must be skipped with a warning, not crash."""
        mock_get.return_value = _fred_response([
            _obs("2024-01-01", "5.33"),
            _obs("2024-02-01", "N/A"),
        ])
        result = _fetch_observations("FEDFUNDS", "key", "2024-01-01", "2024-02-01")
        assert len(result) == 1
        assert result[0]["date"] == "2024-01-01"

    @patch("ingest_macro.requests.get")
    def test_http_400_raises_value_error(self, mock_get):
        """HTTP 400 = bad series ID → ValueError with helpful message."""
        mock_get.return_value = MagicMock(status_code=400)
        with pytest.raises(ValueError, match="400"):
            _fetch_observations("BAD_ID", "key", "2024-01-01", "2024-06-01")

    @patch("ingest_macro.requests.get")
    def test_http_401_raises_permission_error(self, mock_get):
        """HTTP 401 = bad API key → PermissionError."""
        mock_get.return_value = MagicMock(status_code=401)
        with pytest.raises(PermissionError, match="401"):
            _fetch_observations("FEDFUNDS", "bad_key", "2024-01-01", "2024-06-01")

    @patch("ingest_macro.requests.get")
    def test_fred_error_message_in_200_body_raises(self, mock_get):
        """FRED can return HTTP 200 with an error_message field — must raise."""
        mock = MagicMock()
        mock.status_code = 200
        mock.json.return_value = {"error_message": "Bad Request. series_id not found."}
        mock_get.return_value = mock
        with pytest.raises(ValueError, match="error"):
            _fetch_observations("FEDFUNDS", "key", "2024-01-01", "2024-06-01")

    @patch("ingest_macro.requests.get")
    def test_connection_error_raises_runtime_error(self, mock_get):
        """Network failure after retries → RuntimeError."""
        mock_get.side_effect = requests.exceptions.ConnectionError("No route to host")
        with pytest.raises(RuntimeError, match="connect"):
            _fetch_observations("FEDFUNDS", "key", "2024-01-01", "2024-06-01")

    @patch("ingest_macro.requests.get")
    def test_empty_observations_returns_empty_list(self, mock_get):
        mock_get.return_value = _fred_response([])
        result = _fetch_observations("FEDFUNDS", "key", "2024-01-01", "2024-01-31")
        assert result == []


# ── _upsert_macro ─────────────────────────────────────────────────────────────


class TestUpsertMacro:
    def test_inserts_new_rows(self, db):
        obs = [{"date": "2024-01-01", "value": 5.33}, {"date": "2024-02-01", "value": 5.25}]
        assert _upsert_macro(db, "FEDFUNDS", obs) == 2
        assert db.execute("SELECT COUNT(*) FROM raw_macro").fetchone()[0] == 2

    def test_rerun_does_not_duplicate_rows(self, db):
        obs = [{"date": "2024-01-01", "value": 5.33}]
        _upsert_macro(db, "FEDFUNDS", obs)
        _upsert_macro(db, "FEDFUNDS", obs)
        assert db.execute("SELECT COUNT(*) FROM raw_macro").fetchone()[0] == 1

    def test_upsert_replaces_value_on_conflict(self, db):
        _upsert_macro(db, "FEDFUNDS", [{"date": "2024-01-01", "value": 5.33}])
        _upsert_macro(db, "FEDFUNDS", [{"date": "2024-01-01", "value": 5.99}])
        val = db.execute(
            "SELECT indicator_value FROM raw_macro WHERE date='2024-01-01' AND indicator_name='FEDFUNDS'"
        ).fetchone()[0]
        assert val == 5.99

    def test_different_series_stored_separately(self, db):
        _upsert_macro(db, "FEDFUNDS", [{"date": "2024-01-01", "value": 5.33}])
        _upsert_macro(db, "UNRATE", [{"date": "2024-01-01", "value": 3.7}])
        assert db.execute("SELECT COUNT(*) FROM raw_macro").fetchone()[0] == 2


# ── _check_gaps ───────────────────────────────────────────────────────────────


class TestCheckGaps:
    def test_returns_true_for_monthly_data(self, db):
        """Monthly observations have ~30-day gaps — within the 35-day limit."""
        for obs in _monthly(n=6):
            _upsert_macro(db, "FEDFUNDS", [{"date": obs["date"], "value": 5.0}])
        assert _check_gaps(db, "FEDFUNDS") is True

    def test_returns_false_for_large_gap(self, db):
        """A 60-day gap must be flagged."""
        obs = [{"date": "2024-01-01", "value": 5.0}, {"date": "2024-03-01", "value": 5.1}]
        _upsert_macro(db, "FEDFUNDS", obs)
        assert _check_gaps(db, "FEDFUNDS") is False

    def test_returns_true_for_single_observation(self, db):
        """Can't detect a gap with only one row — should return True."""
        _upsert_macro(db, "FEDFUNDS", [{"date": "2024-01-01", "value": 5.0}])
        assert _check_gaps(db, "FEDFUNDS") is True

    def test_gap_exactly_at_limit_is_accepted(self, db):
        """A gap of exactly MAX_MACRO_GAP_DAYS days must pass (strictly greater-than check)."""
        from datetime import datetime
        d2 = (datetime(2024, 1, 1) + timedelta(days=config.MAX_MACRO_GAP_DAYS)).strftime("%Y-%m-%d")
        obs = [{"date": "2024-01-01", "value": 5.0}, {"date": d2, "value": 5.1}]
        _upsert_macro(db, "FEDFUNDS", obs)
        assert _check_gaps(db, "FEDFUNDS") is True


# ── ingest_macro (full function) ──────────────────────────────────────────────


class TestIngestMacro:
    @patch("ingest_macro.requests.get")
    def test_normal_case_populates_db(self, mock_get, db):
        """All series succeed — DB has rows for every series."""
        mock_get.return_value = _fred_response(_monthly(n=24))
        ingest_macro()
        for s in config.FRED_SERIES:
            count = db.execute(
                "SELECT COUNT(*) FROM raw_macro WHERE indicator_name=?", (s,)
            ).fetchone()[0]
            assert count == 24

    @patch("ingest_macro.requests.get")
    def test_incremental_run_requests_delta_only(self, mock_get, db):
        """Existing data triggers an incremental fetch starting the next day."""
        _upsert_macro(db, "FEDFUNDS", [{"date": "2024-06-01", "value": 5.33}])
        mock_get.return_value = _fred_response([_obs("2024-07-01", "5.25")])

        with patch("ingest_macro.FRED_SERIES", ["FEDFUNDS"]):
            ingest_macro()

        params = mock_get.call_args[1]["params"]
        assert params["observation_start"] == "2024-06-02"

    @patch("ingest_macro.requests.get")
    def test_rerun_does_not_duplicate_rows(self, mock_get, db):
        """Running ingest_macro twice must not grow the row count."""
        mock_get.return_value = _fred_response(_monthly(n=12))

        with patch("ingest_macro.FRED_SERIES", ["FEDFUNDS"]):
            ingest_macro()
            first = db.execute("SELECT COUNT(*) FROM raw_macro").fetchone()[0]
            ingest_macro()
            second = db.execute("SELECT COUNT(*) FROM raw_macro").fetchone()[0]

        assert second == first

    @patch("ingest_macro.requests.get")
    def test_http_error_case_triggers_abort_gate(self, mock_get, db):
        """HTTP 400 on any series must raise RuntimeError after the loop."""
        def side_effect(url, params=None, **kwargs):
            if params and params.get("series_id") == "UNRATE":
                return MagicMock(status_code=400)
            return _fred_response(_monthly(n=6))

        mock_get.side_effect = side_effect

        with pytest.raises(RuntimeError, match="UNRATE"):
            ingest_macro()

    @patch("ingest_macro.requests.get")
    def test_missing_api_key_raises_before_any_request(self, mock_get, monkeypatch, db):
        """No HTTP call should be made if FRED_API_KEY is absent."""
        monkeypatch.delenv("FRED_API_KEY", raising=False)
        with pytest.raises(EnvironmentError, match="FRED_API_KEY"):
            ingest_macro()
        mock_get.assert_not_called()

    @patch("ingest_macro.requests.get")
    def test_response_parsing_rejects_non_numeric_values(self, mock_get, db):
        """
        A series that returns only non-numeric values (data quality issue) should
        produce zero rows, be treated as failed, and trigger the abort gate.
        """
        mock_get.return_value = _fred_response([_obs("2024-01-01", "not_a_number")])

        with patch("ingest_macro.FRED_SERIES", ["FEDFUNDS"]):
            with pytest.raises(RuntimeError):
                ingest_macro()

        assert db.execute("SELECT COUNT(*) FROM raw_macro").fetchone()[0] == 0