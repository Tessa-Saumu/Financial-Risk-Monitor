# STRUCTURE.md — Financial Risk Monitor

> Reference guide for every folder and file in this repository.

---

## Top-Level Overview

```
Financial-Risk-Monitor/
├── scripts/                # ETL and pipeline scripts — run these in order
├── models/                 # ML model logic — Prophet and Monte Carlo
├── data/                   # Raw and processed flat files (not the database)
├── database/               # SQLite database file
├── dashboard/              # Power BI .pbix file
├── notebooks/              # Exploration and validation notebooks
├── tests/                  # Unit tests for each pipeline module
├── docs/                   # Schema diagram, refresh workflow, API setup
├── assets/                 # README images and Power BI screenshots
├── config.py               # Central configuration (tickers, paths, settings)
├── run_agent.py            # (not used in this project — see scripts/)
├── requirements.txt        # Python dependencies
├── .env.example            # FRED API key template
├── .gitignore
├── README.md
└── Project Description.md
```

---

## `scripts/` — ETL and Pipeline Scripts

Run these scripts in order to refresh all data and model outputs. They form the data pipeline described in the README's Data Refresh Workflow section.

| File | Run order | Purpose |
|---|---|---|
| `init_db.py` | 0 (once) | Creates the SQLite database and all six tables using `CREATE TABLE IF NOT EXISTS`. Safe to re-run. Must be run once before any other script |
| `ingest_prices.py` | 1 | Pulls historical OHLCV data for every ticker in `config.TICKERS` from Yahoo Finance via `yfinance`. Upserts rows into the `raw_prices` table |
| `ingest_macro.py` | 2 | Calls the FRED REST API for each series in `config.FRED_SERIES`. Upserts rows into the `raw_macro` table. Requires `FRED_API_KEY` in `.env` |
| `compute_risk.py` | 3 | Reads `raw_prices` and computes daily returns, rolling 7-day and 30-day volatility, drawdown, VaR 95%, CVaR 95%, and combined risk scores. Also runs the Monte Carlo simulation. Populates `asset_returns`, `risk_scores`, and `monte_carlo` tables |
| `run_forecasts.py` | 4 | Fits a Prophet model per ticker on historical close prices and generates a 30-day forward outlook. Populates the `forecasts` table |

---

## `models/` — ML Model Logic

Reusable Python modules containing the statistical and ML logic. Scripts in `scripts/` call these — they are not run directly.

### `models/risk_metrics.py`

Core financial risk calculations. Each function is pure (stateless) and independently testable.

| Function | Purpose |
|---|---|
| `daily_returns(prices)` | Percentage change series from a price series |
| `rolling_volatility(returns, window)` | Annualised rolling standard deviation |
| `max_drawdown(prices)` | Running drawdown from peak series |
| `value_at_risk(returns, confidence=0.95)` | Historical VaR at the given confidence level |
| `conditional_var(returns, confidence=0.95)` | Expected Shortfall beyond the VaR threshold (CVaR) |
| `combined_risk_score(*scores)` | Normalises and combines component scores to a single 0–1 signal |

### `models/prophet/forecast.py`

Helper wrapping the Prophet library. Called by `scripts/run_forecasts.py`.

| Function | Purpose |
|---|---|
| `fit_and_forecast(df, horizon)` | Fits Prophet on a `[ds, y]` DataFrame and returns forecast with `yhat`, `yhat_lower`, `yhat_upper` |

### `models/monte_carlo/simulation.py`

Monte Carlo portfolio simulation. Called by `scripts/compute_risk.py`.

| Function | Purpose |
|---|---|
| `simulate(returns_df, weights, n_paths, horizon, initial_value)` | Runs `n_paths` portfolio trajectories using historical return sampling. Returns a DataFrame with `run_id`, `date`, `portfolio_value`, `final_value`, `breach_flag` |

---

## `database/` — SQLite Database

| File | Purpose |
|---|---|
| `financial_risk.db` | The SQLite database file. Created by `scripts/init_db.py`. **Not committed to Git** (listed in `.gitignore` due to binary size) |

### Database Schema

| Table | Key columns | Populated by |
|---|---|---|
| `raw_prices` | date, ticker, open, high, low, close, volume | `ingest_prices.py` |
| `raw_macro` | date, indicator_name, indicator_value | `ingest_macro.py` |
| `asset_returns` | date, ticker, daily_return, rolling_7d_vol, rolling_30d_vol, drawdown | `compute_risk.py` |
| `risk_scores` | date, ticker, var_95, cvar_95, volatility_score, drawdown_score, combined_risk_score | `compute_risk.py` |
| `forecasts` | forecast_date, ticker, target_date, predicted_close, lower_bound, upper_bound | `run_forecasts.py` |
| `monte_carlo` | run_id, date, portfolio_value, final_value, breach_flag | `compute_risk.py` |

---

## `data/` — Flat Files

Used for intermediate exports and any manual data files. The database is the primary store; these are supplementary.

| Folder | Purpose |
|---|---|
| `data/raw/` | Any manually downloaded CSV files (e.g. backup exports from Yahoo Finance or FRED) |
| `data/processed/` | CSV exports from the database used for ad-hoc analysis or sharing without the full DB |

---

## `dashboard/` — Power BI

| File | Purpose |
|---|---|
| `financial_risk_monitor.pbix` | The Power BI Desktop file. Connected to `database/financial_risk.db` via the SQLite ODBC connector. Contains four pages: Portfolio Overview, Risk Analysis, Forecast Page, Scenario Explorer |

### Dashboard Pages

| Page | Content |
|---|---|
| Portfolio Overview | Risk heatmap across all tickers, latest combined risk scores, sparklines for recent price movement |
| Risk Analysis | Rolling 7d and 30d volatility charts, drawdown timeline, VaR/CVaR breakdown per asset |
| Forecast Page | Actual vs predicted close prices per ticker with Prophet confidence bands |
| Scenario Explorer | What-if slicers for interest rate shock and volatility shock — drives conditional formatting on risk scores |

---

## `notebooks/` — Exploration and Development

Jupyter notebooks used during development. Not part of the automated pipeline.

| File | Purpose |
|---|---|
| `01_data_exploration.ipynb` | Initial inspection of raw price and macro data — distributions, date coverage, missing values |
| `02_risk_metrics_dev.ipynb` | Interactive development and visualisation of VaR, CVaR, and combined risk score calculations |
| `03_prophet_tuning.ipynb` | Prophet model experimentation — seasonality settings, changepoint tuning, confidence interval width |
| `04_monte_carlo_analysis.ipynb` | Monte Carlo path visualisation — fan charts, final value histograms, breach probability sensitivity |
| `05_dashboard_data_validation.ipynb` | Validates that database table outputs match what Power BI is displaying — catches stale refresh issues |

---

## `tests/` — Unit Tests

| File | Purpose |
|---|---|
| `test_ingest_prices.py` | Tests Yahoo Finance download, SQLite write, and upsert behaviour |
| `test_ingest_macro.py` | Tests FRED API call, response parsing, and macro table upsert |
| `test_risk_metrics.py` | Tests all functions in `models/risk_metrics.py` — known-value assertions for VaR, CVaR, drawdown |
| `test_prophet_forecast.py` | Tests `fit_and_forecast` — checks output shape, no nulls in yhat, forecast extends correct number of days |
| `test_monte_carlo.py` | Tests `simulate` — checks output row count (n_paths × horizon), breach_flag values, and VaR calculation |

---

## `docs/`

| File | Purpose |
|---|---|
| `schema_diagram.md` | Entity-relationship diagram of all six database tables with primary keys and relationships described |
| `data_refresh_workflow.md` | Step-by-step instructions for running the full pipeline refresh — including what to do if a script fails mid-run |
| `fred_api_setup.md` | How to register for a FRED API key, where to add it in `.env`, and which FRED series are used and why |

---

## `assets/`

| File | Purpose |
|---|---|
| `architecture_diagram.png` | Pipeline diagram (Yahoo Finance + FRED → SQLite → Models → Power BI) used in README |
| `dashboard_overview.png` | Screenshot of the Portfolio Overview page |
| `dashboard_risk.png` | Screenshot of the Risk Analysis page |
| `dashboard_forecast.png` | Screenshot of the Forecast Page |
| `dashboard_scenario.png` | Screenshot of the Scenario Explorer page |

---

## Root Files

| File | Purpose |
|---|---|
| `config.py` | Central configuration — edit `TICKERS`, `FRED_SERIES`, `DB_PATH`, `FORECAST_HORIZON_DAYS`, `MONTE_CARLO_PATHS` here. All scripts import from this file |
| `requirements.txt` | Python dependencies: yfinance, requests, pandas, numpy, prophet, scipy, jupyter, python-dotenv |
| `.env.example` | Template for `FRED_API_KEY` — copy to `.env` and fill in your key |
| `.gitignore` | Excludes `__pycache__`, `.env`, `.ipynb_checkpoints`, and `database/*.db` |
| `README.md` | Project overview, quickstart, architecture diagram, data refresh workflow, and dashboard screenshots |
| `Project Description.md` | Full problem statement, objectives, deliverables, technical constraints, and out-of-scope items |