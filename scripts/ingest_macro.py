"""
ingest_macro.py — pulls macroeconomic indicators from the FRED REST API
and writes them to the raw_macro SQLite table.

Indicators configured in config.py (FRED_SERIES):
  FEDFUNDS, CPIAUCSL, UNRATE, DGS10, and others.

Usage:
    python scripts/ingest_macro.py
"""
import logging
import os
import sqlite3
import time
from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd
import requests

from config import DB_PATH, FRED_SERIES, MAX_MACRO_GAP_DAYS, PRICE_START_DATE

logger = logging.getLogger(__name__)

FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"
REQUEST_TIMEOUT = 30
RETRY_ATTEMPTS = 3
RETRY_BACKOFF = 2  # seconds; multiplied by attempt number


# ── Private helpers ───────────────────────────────────────────────────────────


def _require_api_key() -> str:
    """
    Read FRED_API_KEY from the environment.
    Raises EnvironmentError immediately if missing — better to fail at startup
    than halfway through a loop of API calls.
    """
    key = os.getenv("FRED_API_KEY", "").strip()
    if not key:
        raise EnvironmentError(
            "FRED_API_KEY is not set. Get a free key at "
            "https://fred.stlouisfed.org/docs/api/api_key.html "
            "then: export FRED_API_KEY=your_key"
        )
    return key


def _get_last_stored_date(conn: sqlite3.Connection, series_id: str) -> Optional[str]:
    """Return the most recent date stored for series_id, or None."""
    row = conn.execute(
        "SELECT MAX(date) FROM raw_macro WHERE indicator_name = ?", (series_id,)
    ).fetchone()
    return row[0] if row and row[0] else None


def _fetch_window(last_stored: Optional[str]) -> tuple[str, str]:
    """
    Return (observation_start, observation_end) for the FRED API call.
    FRED end is inclusive, so observation_end = today.

    First run  → PRICE_START_DATE to today.
    Subsequent → last_stored + 1 day to today.
    Already up to date → ("", "") sentinel.
    """
    today = date.today().isoformat()

    if last_stored is None:
        return PRICE_START_DATE, today

    last_date = datetime.strptime(last_stored, "%Y-%m-%d").date()
    next_day = last_date + timedelta(days=1)
    if next_day > date.today():
        return "", ""

    return next_day.isoformat(), today


def _fetch_observations(series_id: str, api_key: str, obs_start: str, obs_end: str) -> list[dict]:
    """
    Call the FRED observations endpoint and return a list of
    {"date": "YYYY-MM-DD", "value": float} dicts, dropping missing values.

    Handles:
      - HTTP 400  → bad series ID        → raises ValueError
      - HTTP 401/403 → bad/expired key   → raises PermissionError
      - HTTP 429  → rate limited         → waits 60 s and retries
      - HTTP 5xx  → server error         → retries with back-off
      - Connection / timeout errors      → retries with back-off
      - "." values → FRED missing data   → silently dropped
      - Non-numeric values               → logged and dropped
      - error_message in 200 body        → raises ValueError
    """
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "observation_start": obs_start,
        "observation_end": obs_end,
        "file_type": "json",
        "sort_order": "asc",
    }

    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            response = requests.get(FRED_BASE_URL, params=params, timeout=REQUEST_TIMEOUT)
        except requests.exceptions.ConnectionError as exc:
            logger.warning("[%s] Connection error (attempt %d/%d): %s", series_id, attempt, RETRY_ATTEMPTS, exc)
            if attempt < RETRY_ATTEMPTS:
                time.sleep(RETRY_BACKOFF * attempt)
                continue
            raise RuntimeError(f"[{series_id}] Could not connect to FRED after {RETRY_ATTEMPTS} attempts.") from exc
        except requests.exceptions.Timeout:
            logger.warning("[%s] Timeout (attempt %d/%d).", series_id, attempt, RETRY_ATTEMPTS)
            if attempt < RETRY_ATTEMPTS:
                time.sleep(RETRY_BACKOFF * attempt)
                continue
            raise RuntimeError(f"[{series_id}] FRED request timed out after {RETRY_ATTEMPTS} attempts.")

        if response.status_code == 400:
            raise ValueError(
                f"[{series_id}] HTTP 400 — series ID may be invalid. "
                f"Check https://fred.stlouisfed.org/series/{series_id}"
            )
        if response.status_code in (401, 403):
            raise PermissionError(
                f"[{series_id}] HTTP {response.status_code} — check FRED_API_KEY is correct."
            )
        if response.status_code == 429:
            logger.warning("[%s] Rate limited — waiting 60 s.", series_id)
            time.sleep(60)
            continue
        if response.status_code >= 500:
            logger.warning("[%s] Server error %d (attempt %d/%d).", series_id, response.status_code, attempt, RETRY_ATTEMPTS)
            if attempt < RETRY_ATTEMPTS:
                time.sleep(RETRY_BACKOFF * attempt)
                continue
            raise RuntimeError(f"[{series_id}] FRED server error {response.status_code} after {RETRY_ATTEMPTS} attempts.")

        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError(f"[{series_id}] FRED response was not valid JSON.") from exc

        if "error_message" in payload:
            raise ValueError(f"[{series_id}] FRED error: {payload['error_message']}")

        clean = []
        for obs in payload.get("observations", []):
            raw = obs.get("value", ".")
            if raw == ".":
                continue  # FRED sentinel for missing/unpublished values
            try:
                clean.append({"date": obs["date"], "value": float(raw)})
            except (ValueError, TypeError):
                logger.warning("[%s] Non-numeric value '%s' on %s — skipping.", series_id, raw, obs.get("date"))

        return clean

    return []  # exhausted retries without raising


def _upsert_macro(conn: sqlite3.Connection, series_id: str, observations: list[dict]) -> int:
    """
    Write observations to raw_macro using INSERT OR REPLACE.
    Column name matches init_db.py schema: indicator_value.
    Returns the number of rows written.
    """
    conn.executemany(
        """
        INSERT OR REPLACE INTO raw_macro (date, indicator_name, indicator_value)
        VALUES (?, ?, ?)
        """,
        [(obs["date"], series_id, obs["value"]) for obs in observations],
    )
    conn.commit()
    return len(observations)


def _check_gaps(conn: sqlite3.Connection, series_id: str) -> bool:
    """
    Check stored dates for series_id for gaps exceeding MAX_MACRO_GAP_DAYS.
    Returns True if clean, False (+ WARNING log) if a gap is found.
    """
    rows = conn.execute(
        "SELECT date FROM raw_macro WHERE indicator_name = ? ORDER BY date ASC",
        (series_id,),
    ).fetchall()

    if len(rows) < 2:
        return True

    dates = [datetime.strptime(r[0], "%Y-%m-%d").date() for r in rows]
    max_gap = timedelta(0)
    gap_location: Optional[tuple] = None

    for i in range(1, len(dates)):
        gap = dates[i] - dates[i - 1]
        if gap > max_gap:
            max_gap = gap
            gap_location = (dates[i - 1], dates[i])

    if max_gap.days > MAX_MACRO_GAP_DAYS:
        logger.warning(
            "  [%s] ⚠ GAP DETECTED — %d days between %s and %s. "
            "Downstream calculations may be unreliable.",
            series_id, max_gap.days, gap_location[0], gap_location[1],
        )
        return False

    logger.info("  [%s] ✓ Continuity OK — max gap %d days.", series_id, max_gap.days)
    return True


# ── Public function ───────────────────────────────────────────────────────────


def ingest_macro(db_path: str = DB_PATH) -> None:
    """
    Fetch and store observations for all series in config.FRED_SERIES.

    - First run  : downloads from PRICE_START_DATE to today.
    - Subsequent : fetches only the delta from the last stored date.
    - Re-run safe: INSERT OR REPLACE on (date, indicator_name) prevents duplicates.
    - Abort gate : raises RuntimeError if any series fails, because all series
                   are required for downstream risk calculations.
    """
    api_key = _require_api_key()  # fail fast before opening the DB

    succeeded, skipped, failed, failed_list, gap_warnings = 0, 0, 0, [], []

    logger.info("=" * 60)
    logger.info("MACRO INGESTION START — %d series", len(FRED_SERIES))
    logger.info("=" * 60)

    conn = sqlite3.connect(db_path)
    try:
        for series_id in FRED_SERIES:
            logger.info("Processing %s", series_id)

            # 1. Work out what window to fetch
            last_stored = _get_last_stored_date(conn, series_id)
            obs_start, obs_end = _fetch_window(last_stored)

            if obs_start == "":
                logger.info("  [%s] Already up to date — skipping.", series_id)
                skipped += 1
                continue

            mode = "incremental" if last_stored else "initial"
            logger.info("  [%s] %s load — fetching %s to %s", series_id, mode, obs_start, obs_end)

            # 2. Call FRED
            try:
                observations = _fetch_observations(series_id, api_key, obs_start, obs_end)
            except (ValueError, PermissionError, RuntimeError) as exc:
                logger.error("  [%s] FAILED: %s", series_id, exc)
                failed += 1
                failed_list.append(series_id)
                continue

            if not observations:
                logger.warning(
                    "  [%s] No observations returned for %s → %s.",
                    series_id, obs_start, obs_end,
                )
                if last_stored is None:
                    failed += 1
                    failed_list.append(series_id)
                else:
                    skipped += 1
                continue

            # 3. Upsert
            written = _upsert_macro(conn, series_id, observations)
            logger.info("  [%s] ✓ %d rows written.", series_id, written)

            # 4. Gap check against full stored history
            if not _check_gaps(conn, series_id):
                gap_warnings.append(series_id)

            succeeded += 1

    finally:
        conn.close()

    # Summary
    logger.info("-" * 60)
    logger.info(
        "Attempted: %d | Succeeded: %d | Skipped: %d | Failed: %d",
        len(FRED_SERIES), succeeded, skipped, failed,
    )
    if failed_list:
        logger.error("Failed series: %s", ", ".join(failed_list))
    if gap_warnings:
        logger.warning("Gap warnings: %s", ", ".join(gap_warnings))

    # Abort gate — all series required for valid risk calculations
    if failed:
        raise RuntimeError(
            f"Macro ingestion failed for: {', '.join(failed_list)}. "
            f"All series in config.FRED_SERIES must return data."
        )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    ingest_macro()