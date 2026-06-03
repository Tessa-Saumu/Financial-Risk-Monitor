# Financial Risk Monitor

> An end-to-end financial analytics pipeline that ingests market and macroeconomic data, computes ML-driven risk metrics, runs Monte Carlo portfolio simulations, and serves a refreshable multi-page Power BI dashboard.

---

## Problem Statement

Investors and analysts monitoring multiple assets rarely have a single, unified view of portfolio risk — especially one that incorporates macroeconomic context alongside price behaviour. Raw price feeds are noisy, risk signals are scattered across tools, and forecasting is often done manually or not at all. This project builds an automated, end-to-end pipeline that collects market and economic data, applies financial ML models, and presents risk-ready insights in a refreshable Power BI dashboard.

---

## Objectives

1. Ingest historical asset price data from Yahoo Finance and macroeconomic indicators from FRED
2. Store raw and processed data in a structured SQLite database
3. Compute core financial risk metrics: returns, rolling volatility, drawdown, Value at Risk (VaR), and Conditional VaR (CVaR)
4. Build a Prophet-based forecasting component per asset with 30-day outlook
5. Run Monte Carlo portfolio simulations (10,000 paths) to model probabilistic risk scenarios
6. Design a Power BI dashboard that refreshes from processed SQLite outputs and includes scenario what-if slicers

---

## Expected Outcomes

- Automated ingestion scripts for Yahoo Finance (yfinance) and FRED API
- SQLite database with raw and processed financial tables
- Risk scoring and Monte Carlo simulation pipeline in Python
- Prophet forecasting model per asset with confidence intervals
- Power BI dashboard (.pbix) with four pages:
  - Portfolio Overview — risk heatmap, latest scores, sparklines
  - Risk Analysis — rolling volatility, drawdown charts, VaR/CVaR breakdown
  - Forecast Page — actual vs predicted prices with confidence bands
  - Scenario Explorer — what-if slicers for interest rate and volatility shocks
- Documented data refresh workflow (run Python scripts → refresh Power BI)
- GitHub repository with README, schema diagram, screenshots, and setup instructions

---

## Architecture

```
Yahoo Finance (yfinance) ──┐
                           ├──▶ Python ETL ──▶ SQLite ──▶ ML Models ──▶ Power BI Desktop
FRED API (requests)   ─────┘                            (Prophet + Monte Carlo)
```

---

## Tech Stack

| Layer | Tools |
|---|---|
| Data ingestion | Python, yfinance, requests |
| Storage | SQLite (sqlite3) |
| Data processing | pandas, numpy |
| Forecasting | Prophet |
| Risk modelling | numpy (Monte Carlo), scipy |
| Visualisation | Power BI Desktop |
| Version control | Git, GitHub |

---

## Database Schema

| Table | Key columns |
|---|---|
| `raw_prices` | date, ticker, open, high, low, close, volume |
| `raw_macro` | date, indicator_name, indicator_value |
| `asset_returns` | date, ticker, daily_return, rolling_7d_vol, rolling_30d_vol, drawdown |
| `risk_scores` | date, ticker, var_95, cvar_95, volatility_score, drawdown_score, combined_risk_score |
| `forecasts` | date, ticker, forecast_date, predicted_close, lower_bound, upper_bound |
| `monte_carlo` | run_id, date, portfolio_value, final_value, breach_flag |

---

## Data Refresh Workflow

1. Run `python scripts/ingest_prices.py` — pulls latest prices from Yahoo Finance into SQLite
2. Run `python scripts/ingest_macro.py` — pulls latest FRED indicators into SQLite
3. Run `python scripts/compute_risk.py` — recalculates risk metrics and Monte Carlo outputs
4. Run `python scripts/run_forecasts.py` — regenerates Prophet forecasts
5. Open the `.pbix` file in Power BI Desktop → click **Refresh** → all visuals update

---

## Setup

```bash
git clone https://github.com/your-username/financial-risk-monitor
cd financial-risk-monitor
pip install -r requirements.txt
cp .env.example .env        # add your FRED API key
python scripts/ingest_prices.py
python scripts/ingest_macro.py
python scripts/compute_risk.py
python scripts/run_forecasts.py
```

Then open `dashboard/financial_risk_monitor.pbix` in Power BI Desktop and refresh.

---

## Project Status

In development — June/July 2026
