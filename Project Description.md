# Project Description — Financial Risk Monitor

## Overview

Financial Risk Monitor is a data analytics project that builds an end-to-end pipeline for monitoring portfolio risk across multiple asset classes using market data, macroeconomic indicators, ML-based forecasting, and a refreshable Power BI dashboard.

The project covers the full analytics lifecycle: raw data ingestion, database storage, feature engineering, forecasting, probabilistic risk simulation, and business intelligence delivery.

---

## Problem

Investors and analysts monitoring multiple assets rarely have a single, unified view of portfolio risk that incorporates both asset-level behaviour and macroeconomic context. Price feeds are noisy, risk signals are fragmented, and forecasting is done manually or not at all. This makes it difficult to assess risk conditions at a glance or explore "what if" scenarios in real time.

---

## Objectives

1. Ingest historical asset price data from Yahoo Finance and macroeconomic indicators from FRED and store them in a structured SQLite database
2. Build a Python pipeline that computes core financial risk metrics: daily returns, rolling volatility (7-day and 30-day), drawdown, Value at Risk (VaR 95%), and Conditional VaR (CVaR)
3. Produce a combined risk score per asset that aggregates the individual metrics into a single 0–1 signal
4. Build a Prophet-based forecasting component that generates 30-day price outlooks with confidence intervals per asset
5. Run Monte Carlo portfolio simulations (10,000 paths) to model the probability of significant drawdowns under different conditions
6. Build a Power BI dashboard (.pbix) connected to the processed SQLite outputs, with four report pages including a scenario explorer with interactive slicers

---

## Expected Outcomes

### Deliverable 1 — Data ingestion scripts
Python scripts that pull data from Yahoo Finance (via yfinance) and the FRED API, validate the outputs, and write them to the appropriate raw SQLite tables.

### Deliverable 2 — SQLite database
A structured SQLite database with six tables covering raw prices, raw macro indicators, computed returns and volatility, risk scores, Prophet forecasts, and Monte Carlo simulation results.

### Deliverable 3 — Risk computation pipeline
A Python module that reads from raw tables and produces fully populated risk_scores and asset_returns tables, including the combined risk score per asset per day.

### Deliverable 4 — Forecasting model
A per-asset Prophet forecasting pipeline that produces a 30-day forward outlook with upper and lower confidence bounds, stored in the forecasts table.

### Deliverable 5 — Monte Carlo simulation
A simulation module that runs 10,000 portfolio paths from the current date, computing final portfolio value distribution, VaR, CVaR, and breach probability.

### Deliverable 6 — Power BI dashboard
A .pbix file connected to SQLite with four pages:
- Portfolio Overview (risk heatmap, sparklines, latest scores)
- Risk Analysis (rolling volatility, drawdown, VaR/CVaR breakdown)
- Forecast Page (actual vs predicted with confidence bands)
- Scenario Explorer (slicers for interest rate and volatility shock inputs)

### Deliverable 7 — Documentation
A GitHub repository with a README, database schema diagram, Power BI screenshot gallery, setup instructions, and a documented data refresh workflow.

---

## Technical Constraints and Assumptions

- Data sources: Yahoo Finance (yfinance library) and FRED (public REST API, free key required)
- Storage: SQLite — chosen for zero-config local use and native Power BI connector support
- Asset universe: 10–15 tickers across equities, crypto, and ETFs (defined in a config file)
- Macro indicators: 5–8 FRED series (e.g. FEDFUNDS, CPIAUCSL, UNRATE, DGS10)
- Forecasting: Prophet only — no deep learning models in scope
- Simulations: Monte Carlo using historical return distribution — no options pricing or Black-Scholes in scope
- Power BI: Desktop only (no Power BI Service or gateway required for MVP)
- No live streaming or real-time data — scheduled batch refresh via Python scripts

---

## Tech Stack

Python, pandas, numpy, SQLite, yfinance, requests, Prophet, scipy, Power BI Desktop

---

## Out of Scope

- Live or streaming data feeds
- Production deployment or scheduling infrastructure
- Advanced portfolio optimisation (Markowitz, Black-Litterman)
- Deep learning forecasting models
- Power BI Service publishing or gateway setup
- DAX measure generation
- LLM or agent-based components (those belong to Project 2)
