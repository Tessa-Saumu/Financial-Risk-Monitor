"""
ingest_prices.py — pulls historical asset price data from Yahoo Finance
via yfinance and writes OHLCV rows to the raw_prices SQLite table.

Usage:
    python scripts/ingest_prices.py
"""
import logging
import sqlite3
from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd
import yfinance as yf

from config import DB_PATH, MIN_ROWS_PER_TICKER, MIN_TICKERS_REQUIRED, PRICE_START_DATE, TICKERS

logger = logging.getLogger(__name__)


# ── Private helpers ───────────────────────────────────────────────────────────


def _get_last_stored_date(conn: sqlite3.Connection, ticker: str) -> Optional[str]:
    """Return the most recent date stored for ticker, or None if no rows exist yet."""
    row = conn.execute(
        "SELECT MAX(date) FROM raw_prices WHERE ticker = ?", (ticker,)
    ).fetchone()
    return row[0] if row and row[0] else None


def _fetch_window(last_stored: Optional[str]) -> tuple[str, str]:
    """
    Return (start, end) for the yfinance download call.

    First run  → start = PRICE_START_DATE, end = tomorrow (yfinance end is exclusive).
    Subsequent → start = last_stored + 1 day, end = tomorrow.
    Already up to date → returns ("", "") as a sentinel so the caller can skip.
    """
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    if last_stored is None:
        return PRICE_START_DATE, tomorrow

    last_date = datetime.strptime(last_stored, "%Y-%m-%d").date()
    next_day = last_date + timedelta(days=1)
    if next_day > date.today():
        return "", ""  # already up to date

    return next_day.isoformat(), tomorrow


def _download_ticker(ticker: str, start: str, end: str) -> Optional[pd.DataFrame]:
    """
    Wrapper around yfinance.download() that normalises columns and returns
    None for empty/failed responses.

    Note: yfinance does NOT raise on a bad ticker — it silently returns an
    empty DataFrame, so we check df.empty explicitly.
    """
    try:
        df = yf.download(
            tickers=ticker,
            start=start,
            end=end,
            auto_adjust=True,
            progress=False,
            threads=False,
        )
    except Exception as exc:
        logger.warning("[%s] Unexpected download error: %s", ticker, exc)
        return None

    if df is None or df.empty:
        logger.warning("[%s] No data returned — ticker may be invalid or delisted.", ticker)
        return None

    # Flatten MultiIndex columns that yfinance produces when auto_adjust=True
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0].lower() for col in df.columns]
    else:
        df.columns = [c.lower() for c in df.columns]

    required = {"open", "high", "low", "close", "volume"}
    if not required.issubset(df.columns):
        logger.warning("[%s] Unexpected columns from yfinance: %s", ticker, list(df.columns))
        return None

    return df


def _upsert_prices(conn: sqlite3.Connection, rows: list[tuple]) -> int:
    """
    Write rows to raw_prices using INSERT OR REPLACE.
    Each tuple: (date, ticker, open, high, low, close, volume).
    Returns the number of rows written.
    """
    conn.executemany(
        """
        INSERT OR REPLACE INTO raw_prices
            (date, ticker, open, high, low, close, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    return len(rows)


# ── Public function ───────────────────────────────────────────────────────────


def ingest_prices(db_path: str = DB_PATH) -> None:
    """
    Download OHLCV data for all tickers in config.TICKERS and write to raw_prices.

    - First run  : downloads from PRICE_START_DATE to today.
    - Subsequent : fetches only the delta from the last stored date.
    - Re-run safe: INSERT OR REPLACE on (date, ticker) prevents duplicates.
    - Abort gate : raises RuntimeError if fewer than MIN_TICKERS_REQUIRED succeed,
                   so the downstream pipeline does not run on insufficient data.
    """
    succeeded, skipped, failed, failed_list = 0, 0, 0, []

    logger.info("=" * 60)
    logger.info("PRICE INGESTION START — %d tickers", len(TICKERS))
    logger.info("=" * 60)

    conn = sqlite3.connect(db_path)
    try:
        for ticker in TICKERS:
            logger.info("Processing %s", ticker)

            # 1. Work out what window to fetch
            last_stored = _get_last_stored_date(conn, ticker)
            start, end = _fetch_window(last_stored)

            if start == "":
                logger.info("  [%s] Already up to date — skipping.", ticker)
                skipped += 1
                continue

            mode = "incremental" if last_stored else "initial"
            logger.info("  [%s] %s load — fetching %s to %s", ticker, mode, start, end)

            # 2. Download
            df = _download_ticker(ticker, start, end)
            if df is None:
                failed += 1
                failed_list.append(ticker)
                continue

            # 3. Upsert
            rows = [
                (
                    idx.strftime("%Y-%m-%d"),
                    ticker,
                    row["open"],
                    row["high"],
                    row["low"],
                    row["close"],
                    row["volume"],
                )
                for idx, row in df.iterrows()
            ]
            written = _upsert_prices(conn, rows)

            # 4. Validate row count on initial load only
            if last_stored is None:
                total = conn.execute(
                    "SELECT COUNT(*) FROM raw_prices WHERE ticker = ?", (ticker,)
                ).fetchone()[0]
                if total < MIN_ROWS_PER_TICKER:
                    logger.warning(
                        "  [%s] Only %d rows — expected > %d from %s. "
                        "Ticker may have limited history.",
                        ticker, total, MIN_ROWS_PER_TICKER, PRICE_START_DATE,
                    )
                else:
                    logger.info("  [%s] ✓ %d total rows in DB.", ticker, total)
            else:
                logger.info("  [%s] ✓ %d new rows written.", ticker, written)

            succeeded += 1

    finally:
        conn.close()

    # Summary
    logger.info("-" * 60)
    logger.info(
        "Attempted: %d | Succeeded: %d | Skipped: %d | Failed: %d",
        len(TICKERS), succeeded, skipped, failed,
    )
    if failed_list:
        logger.warning("Failed tickers: %s", ", ".join(failed_list))

    # Abort gate
    meaningful = succeeded + skipped
    if meaningful < MIN_TICKERS_REQUIRED:
        raise RuntimeError(
            f"Only {meaningful} ticker(s) loaded (minimum: {MIN_TICKERS_REQUIRED}). "
            f"Review config.TICKERS and confirm the symbols are valid on Yahoo Finance."
        )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    ingest_prices()