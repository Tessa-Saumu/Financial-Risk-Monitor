# Data Refresh Workflow

This document describes how to refresh the Financial Risk Monitor end to end: pulling new
market/macro data, recomputing risk metrics and forecasts, and updating the Power BI dashboard
to reflect the changes.

---

## Overview

```
ingest_prices.py ──┐
                    ├──▶ compute_risk.py ──▶ run_forecasts.py ──▶ Power BI Refresh
ingest_macro.py  ───┘
```

Each script writes to `database/financial_risk.db`. Power BI does not talk to the Python
scripts directly — it reads whatever is currently in the SQLite database at the time you click
**Refresh**. This means the scripts must be run *before* refreshing the dashboard, and in the
order below, since `compute_risk.py` and `run_forecasts.py` depend on tables populated by the
earlier steps.

---

## Step 1 — Run the ingestion scripts

From the project root, run each ingestion script as a module:

```bash
python -m scripts.ingest_prices
python -m scripts.ingest_macro
```

- `ingest_prices` pulls the latest asset prices from Yahoo Finance into `raw_prices`.
- `ingest_macro` pulls the latest macroeconomic indicators from FRED into `raw_macro`.

These two can be run in either order relative to each other, but both must complete before
Step 2.

## Step 2 — Recompute risk metrics

```bash
python -m scripts.compute_risk
```

This reads the freshly ingested `raw_prices` and `raw_macro` tables and recalculates
`asset_returns`, `risk_scores`, and `monte_carlo` (10,000-path simulation). This step must run
**after** ingestion and **before** forecasting, since forecasting is independent of this step's
output but the dashboard's risk visuals (Pages 1, 2, and 4) depend on it.

## Step 3 — Regenerate forecasts

```bash
python -m scripts.run_forecasts
```

Regenerates the Prophet-based 30-day forecast per asset into the `forecasts` table
(`predicted_close`, `lower_bound`, `upper_bound`). This step depends on `raw_prices` from Step 1
but not on `compute_risk.py`'s output, though it is run last by convention to keep the workflow
sequential and simple to follow.

## Step 4 — Refresh the Power BI dashboard

1. Open `dashboard/financial_risk_monitor.pbix` in Power BI Desktop.
2. Click **Home → Refresh** on the ribbon.
3. Power BI re-queries all six tables (`raw_prices`, `raw_macro`, `asset_returns`,
   `risk_scores`, `forecasts`, `monte_carlo`) from `database/financial_risk.db` via the
   configured SQLite ODBC connection.
4. All visuals across all four pages update automatically once the refresh completes — no
   manual visual reconfiguration is needed.

---

## Optional — verify before/after

`scripts/verify_acceptance_criteria.py` and `scripts/init_db.py` also exist in the scripts
folder. `init_db.py` is only needed for a first-time/empty database setup and is not part of
the regular refresh cycle. `verify_acceptance_criteria.py` can be run after Step 3 as a sanity
check on row counts and table integrity before opening Power BI, if you want to confirm the
data landed correctly before refreshing the dashboard.

```bash
python -m scripts.verify_acceptance_criteria
```

---

## Important notes on the Scenario Explorer page

The **Interest Rate Shock** and **Volatility Multiplier** What-If sliders on the Scenario
Explorer page operate entirely within Power BI via DAX measures. They do **not** trigger any
Python script and do **not** re-run the Monte Carlo simulation. Moving these sliders only
recalculates the `Adjusted Risk Score` card using a DAX approximation formula. The Monte Carlo
fan chart (P5/P50/P95 paths) always reflects the most recently computed simulation from
`compute_risk.py` (Step 2 above) and only changes when the underlying data is regenerated and
the dashboard is refreshed — not when the sliders are moved.

The `Adjusted Risk Score` measure is:

```
Adjusted Risk Score =
VAR BaseScore = [Latest Risk Score]
VAR VolMult = SELECTEDVALUE('Volatility Multiplier'[Volatility Multiplier], 1)
VAR RateShock = SELECTEDVALUE('Interest Rate Shock'[Interest Rate Shock], 0)
RETURN
    BaseScore * VolMult * (1 + RateShock * 0.01)
```

The Volatility Multiplier scales the base score directly (a 2x multiplier doubles the risk
score contribution), and the Interest Rate Shock is applied as a percentage adjustment
proportional to the base score, rather than a flat additive nudge — so the same rate shock
moves a high-risk ticker's score more than a low-risk ticker's, which better reflects how risk
sensitivity behaves in practice. The 0.01 coefficient (converting the shock input into a
percentage) is a fixed assumption for demonstration purposes and is not derived from the
underlying data. It should be revisited if this measure is used for anything beyond
illustrating how the scenario mechanism works.

---

## Summary checklist

- [ ] `python -m scripts.ingest_prices`
- [ ] `python -m scripts.ingest_macro`
- [ ] `python -m scripts.compute_risk`
- [ ] `python -m scripts.run_forecasts`
- [ ] Open `.pbix` → Home → Refresh
- [ ] Confirm all four pages show updated values (spot-check one ticker's Latest Risk Score
      or sparkline against the database)
