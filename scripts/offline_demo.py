"""Demonstrate idempotent price writes and risk arithmetic on synthetic data."""
import json
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

import pandas as pd

from models.risk_metrics import daily_returns, max_drawdown, value_at_risk
from scripts.ingest_prices import _upsert_prices
from scripts.init_db import init_db


def main() -> None:
    """Use a disposable SQLite database; emit deterministic synthetic evidence."""
    with tempfile.TemporaryDirectory() as folder:
        db = str(Path(folder) / "demo.db")
        init_db(db)
        rows = [(f"2026-01-{day:02d}", "DEMO", price, price, price, price, 100)
                for day, price in zip((1, 2, 3), (100.0, 110.0, 99.0))]
        with closing(sqlite3.connect(db)) as conn:
            _upsert_prices(conn, rows)
            _upsert_prices(conn, rows)
            count = conn.execute("SELECT COUNT(*) FROM raw_prices").fetchone()[0]
        prices = pd.Series([100.0, 110.0, 99.0])
        returns = daily_returns(prices).dropna()
        assert count == 3
        assert abs(float(returns.iloc[0]) - 0.1) < 1e-12
        assert abs(float(returns.iloc[1]) + 0.1) < 1e-12
        assert abs(value_at_risk(returns) + 0.09) < 1e-12
        assert abs(float(max_drawdown(prices).iloc[-1]) + 0.1) < 1e-12
        print(json.dumps({"input": "synthetic, not market data", "rows_after_two_writes": count,
                          "returns": returns.tolist(), "drawdown": -0.1,
                          "historical_var_95": value_at_risk(returns)}, indent=2))


if __name__ == "__main__":
    main()
