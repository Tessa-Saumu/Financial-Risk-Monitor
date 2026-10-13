# SQLite schema and population order

Schema source: scripts/init_db.py (SCHEMA_SQL); no foreign keys are declared.

| Table | Primary key | Populated by | Meaning |
|---|---|---|---|
| raw_prices | date,ticker | ingest_prices | OHLCV observations |
| raw_macro | date,indicator_name | ingest_macro | FRED observations; unused downstream |
| asset_returns | date,ticker | compute_risk | returns, volatility, drawdown |
| risk_scores | date,ticker | compute_risk | historical VaR/CVaR and heuristic score |
| forecasts | date,ticker,forecast_date | run_forecasts | predicted date, ticker, originating forecast date |
| monte_carlo | run_id,date | compute_risk | simulated portfolio paths and breach flag |

Price-derived tables align by ticker/date by convention, not enforced relations. Initialize first; ingest prices before analytics/forecasts. Macro ingestion is independent and does not drive current metrics. Monte Carlo is portfolio-level; it has no ticker key. Dashboard sliders adjust existing scores using DAX; they do not rerun simulations. Forecast dates follow business-day or crypto-calendar conventions described in the scripts.
