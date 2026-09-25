Project Evidence — Financial Risk Monitor

Context

When: Initial commit 2026-06-03 (71dfa57), scaffold through data ingestion late June, risk metrics and Monte Carlo early July, Prophet forecast early-mid July, dashboard build mid July, testing polish and v1.0.0 tag 2026-07-22 (commit 130d5cd, tag v1.0.0). Development window June–July 2026 per git log and README Project Status.

Why it existed: Per `Project Description.md` and `README.md`, to build an end-to-end analytics pipeline that unifies fragmented portfolio risk signals (volatility, drawdown, VaR/CVaR, forecasts, scenario analysis) into a single refreshable Power BI dashboard, covering the full lifecycle: ingestion (Yahoo Finance + FRED), storage (SQLite), risk computation, forecasting, Monte Carlo simulation, BI delivery. Technical constraints document states out-of-scope: live streaming, production scheduling, advanced portfolio optimisation, deep learning, Power BI Service.

Solo / team: Repository `Tessa-Saumu/Financial-Risk-Monitor` owned by Tessa-Saumu. Git shortlog shows 41 commits by Tessa-Saumu, 7 by Adeyeri Michael (merge commits via GitHub noreply), 3 by Theresia (Tessa) Saumu, 2 by Michael Adeyeri. GitHub PRs #1-#14 merged by Adeyeri Michael. Issues #1-#7 closed. No CONTRIBUTORS file. Evidence suggests solo development by Tessa-Saumu with Adeyeri Michael as reviewer/merger, but team structure cannot be definitively proven from repo alone.

My role: If you are Tessa-Saumu / Theresia Saumu, git history attributes the vast majority of code changes to you. However, repository evidence alone does not prove portfolio ownership — there is no signed commit email verification or explicit authorship declaration linking the portfolio candidate to the GitHub handle. Explicitly stating: authorship boundary cannot be proven from repository alone; if you are not Tessa-Saumu, you cannot claim ownership.

Problem

What problem was actually being solved?

Implemented: Batch ETL + risk analytics for a fixed 11-ticker universe (equities: AAPL, MSFT, GOOGL, AMZN, JPM; ETFs: SPY, QQQ, TLT, GLD; crypto: BTC-USD, ETH-USD per `config.py:TICKERS`). Pipeline: `scripts/init_db.py` creates 6 SQLite tables; `ingest_prices.py` pulls OHLCV via yfinance into `raw_prices`; `ingest_macro.py` pulls 5 FRED series (FEDFUNDS, CPIAUCSL, UNRATE, DGS10, VIXCLS per `config.py:FRED_SERIES`) into `raw_macro`; `compute_risk.py` computes daily returns, rolling 7d/30d vol, drawdown into `asset_returns`, rolling VaR/CVaR + combined 0-1 score into `risk_scores`, and 10k-path historical-bootstrap Monte Carlo into `monte_carlo`; `run_forecasts.py` fits per-ticker Prophet models with asset-class-tuned `changepoint_prior_scale` into `forecasts` (30-day horizon). Power BI .pbix (`dashboard/financial_risk_monitor.pbix`, 7.7M) reads SQLite for 4 pages: Portfolio Overview, Risk Analysis, Forecast, Scenario Explorer with DAX-only sliders.

Distinguished from aspirational README language: README Problem Statement talks about “how risky is my portfolio right now, and how would a rate shock change that?” implying real-time risk. Actual implementation is explicitly NOT live — README Known Limitations states “Not live data. Prices and macro indicators are only as current as the last manual run… there's no scheduler or streaming connection.” Scenario Explorer is described as approximation, not re-simulation (DAX formula, not Python rerun). Macro ingestion (`raw_macro`) is documented as not wired into any risk calculation or visual — ingested for future use. So real problem solved is reproducible batch risk reporting, not real-time monitoring or true what-if re-simulation.

What I personally built

Exact components/features/code owned by me.

If candidate is Tessa-Saumu, confirmed ownership via commit history (41 commits) and issue-to-PR mapping:

- Database schema: `scripts/init_db.py` SCHEMA_SQL defines 6 tables with PKs (date,ticker), (date,indicator_name), (date,ticker,forecast_date), (run_id,date). Verified file exists and matches `docs/schema_diagram.md` description.
- Ingestion: `scripts/ingest_prices.py` functions `_fetch_window`, `_get_last_stored_date`, `_download_ticker`, `_upsert_prices`, `ingest_prices` with incremental logic, abort gate `MIN_TICKERS_REQUIRED`. `scripts/ingest_macro.py` functions `_require_api_key`, `_fetch_window`, `_fetch_observations` with 400/401/429/5xx handling, `_upsert_macro`, `_check_gaps`, `ingest_macro`.
- Risk metrics: `models/risk_metrics.py` 6 pure functions: `daily_returns` (pct_change dropna), `rolling_volatility` (annualised sqrt(ppy)), `max_drawdown` (cummax), `value_at_risk` (quantile 1-confidence), `conditional_var` (tail mean), `combined_risk_score` (equal-weight default, validation).
- Monte Carlo: `models/monte_carlo/simulation.py` `simulate` vectorized bootstrap, `_weighted_portfolio_returns` requiring overlapping dates, breach logic `final_value < initial*(1-threshold)`. `scripts/compute_risk.py` functions `compute_returns`, `compute_risk_scores`, `run_monte_carlo`, `_is_crypto_ticker` (uses `config.ASSET_CLASS`), `_periods_per_year`, `_min_max_normalize`, `_resolve_portfolio_weights`.
- Forecasting: `models/prophet/forecast.py` `fit_and_forecast` with Prophet, daily_seasonality False, weekly/yearly True, US holidays, interval_width param, freq B vs D handling. `scripts/run_forecasts.py` `run_forecasts`, `_changepoint_prior_scale_for` using `CHANGEPOINT_PRIOR_SCALE_BY_ASSET_CLASS`.
- Config: `config.py` defines DB_PATH, TICKERS, ASSET_CLASS mapping, FRED_SERIES, PRICE_START_DATE=2020-01-01, FORECAST_HORIZON_DAYS=30, MIN_ROWS_FOR_FORECAST=200, PROPHET_INTERVAL_WIDTH=0.95, CHANGEPOINT_PRIOR_SCALE_BY_ASSET_CLASS {crypto:2.0, equity:0.5, etf:0.1}, MONTE_CARLO_PATHS=10_000, PORTFOLIO_WEIGHTS=None, MONTE_CARLO_DRAWDOWN_THRESHOLD=0.20, MONTE_CARLO_RUNTIME_BUDGET_SECONDS=120, validation thresholds.
- Tests: 5 test files, 98 tests total (22 in test_risk_metrics.py, 19 in test_ingest_prices.py, 31 in test_ingest_macro.py, 10 in test_monte_carlo.py, 16 in test_prophet_forecast.py per pytest collection).
- Documentation: `README.md` (206 lines), `STRUCTURE.md` (190 lines), `docs/data_refresh_workflow.md`, `docs/fred_api_setup.md`, `docs/schema_diagram.md` (empty in current checkout but referenced), `Project Description.md`.
- Dashboard: `dashboard/financial_risk_monitor.pbix` plus 4 screenshots in `assets/` and architecture diagram.
- Notebook: `notebooks/03_prophet_tuning.ipynb` (875 lines) with full CV grid search reasoning, MAPE table, U-shape verification.

Separate confirmed ownership from unclear ownership: Commit history attributes these to Tessa-Saumu, but if portfolio candidate is not Tessa-Saumu, ownership cannot be claimed. Additionally, merge commits by Adeyeri Michael suggest code review but not code authorship. No co-authored-by trailers. 4 other notebooks are empty stubs (01_data_exploration.ipynb 17 lines empty markdown, 02,04,05 are 0 bytes) — no evidence of work.

Architecture

Frontend: Power BI Desktop .pbix (`dashboard/financial_risk_monitor.pbix`) with 4 pages. No web frontend, no Streamlit (mentioned as potential extension). Screenshots in `assets/` prove visuals existed at time of capture: risk heatmap, sparklines, volatility charts, drawdown area, VaR/CVaR bars, actual vs predicted with confidence band, Scenario Explorer sliders. DAX measure for Adjusted Risk Score documented in `docs/data_refresh_workflow.md` as `BaseScore * VolMult * (1 + RateShock * 0.01)`. Frontend is verified as file exists, but cannot be independently verified without Power BI Desktop + SQLite ODBC driver.

Backend: No API server, no backend service. Python scripts act as batch pipeline, not a service. `config.py` is central config. Scripts use `python -m scripts.*` module syntax. No FastAPI/Flask/Django. `requirements.txt` lists yfinance, requests, pandas, numpy, openpyxl, prophet, scipy, jupyter, ipykernel, python-dotenv, rich.

Data: Sources: Yahoo Finance via yfinance (OHLCV), FRED REST API via requests (macro). Storage: SQLite file `database/financial_risk.db` (gitignored per `.gitignore:database/*.db`, and folder does not exist in checkout). Tables: raw_prices, raw_macro, asset_returns, risk_scores, forecasts, monte_carlo. Data flow: ingest_prices + ingest_macro -> compute_risk (returns -> risk_scores -> monte_carlo) -> run_forecasts -> Power BI Refresh. Flat file folders `data/raw/.gitkeep` and `data/processed/.gitkeep` exist but empty.

ML/AI: Prophet forecasting per ticker (univariate time series, ds=y date, y=close). Monte Carlo historical bootstrap (not parametric, preserves fat tails). Risk metrics are statistical, not ML.

Database: SQLite via Python stdlib sqlite3. Schema defined in `scripts/init_db.py:SCHEMA_SQL`. No ORM, no migrations. Uses INSERT OR REPLACE for idempotency, BEGIN transactions, 30s timeout via `_connect`. Primary keys prevent duplicates.

Infrastructure: No containers (no Dockerfile, docker-compose), no CI/CD (no .github/workflows, no Jenkins, no circle), no deployment config, no scheduler (README says cron/Task Scheduler is potential extension). Local-only, manual runs. `.env.example` shows FRED_API_KEY template, `.gitignore` excludes `.env`, `__pycache__`, `.venv`, `database/*.db`.

Major data/control flows: (1) init_db creates tables. (2) ingest_prices: for each ticker in TICKERS, get last stored date, fetch window, download, upsert, validate MIN_ROWS_PER_TICKER, abort if meaningful < MIN_TICKERS_REQUIRED. (3) ingest_macro: require API key fail-fast, for each FRED_SERIES, fetch window, call FRED with retry/backoff/429 handling, parse '.' missing values, upsert, check gaps > MAX_MACRO_GAP_DAYS, abort if any series fails. (4) compute_risk: compute_returns reads raw_prices, computes returns/vol/drawdown with crypto vs equity annualisation (365 vs 252 via ASSET_CLASS), writes asset_returns; compute_risk_scores reads asset_returns, rolling VAR_LOOKBACK_WINDOW=252, MIN_VAR_OBSERVATIONS=30, computes VaR/CVaR, min-max normalizes per ticker, combines; run_monte_carlo reads asset_returns, pivots wide, resolves weights (equal if None, renormalise if sum !=1), runs simulate (10k x 30), writes monte_carlo, logs VaR/CVaR/breach probability. (5) run_forecasts: reads raw_prices, skips if <200 rows, checks staleness >3 days, picks freq D for crypto else B, looks up changepoint_prior_scale, calls fit_and_forecast, writes forecasts with forecast_date=today, idempotent delete per ticker per day. (6) Power BI reads SQLite via ODBC.

ML / AI work

Problem formulation: Time series forecasting: predict next 30 close prices per asset given historical close prices. Risk modelling: estimate tail risk (VaR/CVaR) and breach probability via historical simulation. Combined risk score: aggregate normalized risk components into 0-1 signal. All implemented and verified in code.

Target: Forecasting target is `close` price (y), ds=date. Risk target is daily_return distribution and derived metrics. Monte Carlo target is portfolio_value final distribution. Verified in `models/prophet/forecast.py:fit_and_forecast` expects ds,y; `scripts/run_forecasts.py` renames close to y; `models/risk_metrics.py:daily_returns` operates on price series.

Features: Prophet uses only time features (trend, weekly/yearly seasonality, US holidays) — no exogenous features, no macro integration. Risk metrics use only price-derived features: daily_return, rolling_7d_vol, rolling_30d_vol, drawdown, var_95, cvar_95. Macro features from raw_macro not used downstream (README Known Limitations explicitly says not wired). Verified by searching compute_risk.py — no reference to raw_macro table except comment.

Baseline: No explicit baseline model documented. Prophet tuning notebook compares changepoint_prior_scale values within Prophet, not against naive baseline (e.g., last value, moving average). No baseline for risk metrics (e.g., equal weight). Absent/not applicable.

Models: Prophet (Facebook/Meta) with tuned changepoint_prior_scale per asset class (crypto 2.0, equity 0.5, etf 0.1) derived from notebook 03. Monte Carlo historical bootstrap (10k paths x 30 days) using numpy vectorized choice. No deep learning, no ensemble. Implemented and verified: `models/prophet/forecast.py` uses Prophet, `models/monte_carlo/simulation.py` uses numpy.

Validation methodology: For risk metrics: known-value unit tests in `tests/test_risk_metrics.py` (e.g., VaR on flat positive series, drawdown dip, volatility annualisation). For Monte Carlo: zero-volatility test ensures identical paths, breach flag logic test, runtime budget test (10k x 30 <120s). For Prophet: unit tests on synthetic business-day and calendar-day series (500 rows) checking row count = horizon, no NaNs, bounds ordering lower <= yhat <= upper, input validation (missing column, NaN in y). Pipeline test seeds temp SQLite with 600 rows per ticker and tests forecast_date=today, horizon rows per ticker, thin ticker skipped, idempotent rerun. For tuning: notebook 03 uses Prophet's rolling-origin cross_validation with initial=730 days, period=90 days, horizon=30 days, scoring MAPE (scale-free, avoids BTC dominating RMSE). Grid CANDIDATE_VALUES [0.001,0.01,0.05,0.1,0.5,1.0,2.0,5.0,8.0,12.0] log scale, checks U-shape reversal to confirm optimum not at edge. Documented per-ticker minima: AAPL 0.5 MAPE 5.85%, JPM 0.5 5.52%, SPY 0.05 3.23%, TLT 0.5 2.84%, BTC-USD 1.0 13.72%, ETH-USD 5.0 18.11%. Aggregated per class minima: equity 0.5, etf 0.1 (compromise between 0.05 and 0.5), crypto 2.0 (between 1.0 and 5.0). This is implemented and verified in notebook outputs.

Metrics: VaR 95% (historical quantile), CVaR 95% (expected shortfall), breach probability, rolling volatility, drawdown, combined risk score 0-1, MAPE for tuning (per notebook). Final result: Notebook reports best MAPE per class ~5.7% equity, 3.18% etf, 16.15% crypto. However, these are tuning CV results, not held-out test set final forecast accuracy, and only on 2 representative tickers per class (REPRESENTATIVE_TICKERS). No final model evaluation on unseen data, no backtest of forecast vs actual after v1.0.0. So metrics are documented but not independently reproduced without running notebook (requires DB with 2020-2026 data). Risk metrics have no accuracy metric, only correctness tests.

For each item, distinguish:

- implemented and verified: risk metric functions, Monte Carlo simulation logic, Prophet wrapper, per-asset-class tuning via notebook, pipeline orchestration, idempotent upserts, incremental fetch, abort gates, validation thresholds.
- documented but not reproduced: dashboard visuals (screenshots exist but .pbix cannot be opened in this environment), end-to-end pipeline run (no DB file, no FRED key, no live yfinance test), MAPE numbers from notebook (documented in notebook output but not re-ran here).
- absent/not applicable: baseline models, feature engineering beyond price, macro integration, hyperparameter tuning for Monte Carlo, model registry, experiment tracking.

Do not call something successful merely because a model achieved a metric. Evaluate whether the validation methodology supports the claim: Tuning methodology is sound (MAPE, CV, U-shape check, log scale) but limited to 2 tickers per class, 5-7 folds per ticker (small), no statistical significance testing, and top 2-3 candidates within few percent (author notes this is fold noise). Final chosen values are compromise, not per-ticker optima, which is reasonable but not proven optimal for other tickers (QQQ, GLD, GOOGL, AMZN etc not tested). No final forecast accuracy reported on holdout.

Engineering evidence

Tests: 98 tests across 5 files, all passing when run with venv (verified: 72 in first run, 26 in second, total 98). Types:

- test_risk_metrics.py (22): known-value assertions for daily_returns, rolling_volatility constant/annualisation/custom ppy/warmup NaN, max_drawdown increasing/dip, VaR flat positive vs loss tail, empty raises, CVaR <= VaR, tail mean, combined_risk_score bounds/equal weight/custom weights/out-of-range/bad weights/no scores. What they test: pure function correctness, edge cases (all-null prices), input validation.
- test_ingest_prices.py (19): TestFetchWindow (config start, incremental, up-to-date sentinel), TestGetLastStoredDate (None, most recent, ticker-specific), TestUpsertPrices (insert, no duplicate, replace, multiple tickers), TestDownloadTicker (valid, empty, exception, missing columns), TestIngestPrices (normal populates DB, incremental delta only, rerun no duplicates, failed ticker counted, abort gate, http error). Mocked yfinance.
- test_ingest_macro.py (31): TestRequireApiKey (missing, whitespace, present), TestFetchWindow, TestFetchObservations (normal parse float, drops '.' , drops non-numeric, HTTP 400 ValueError, 401 PermissionError, error_message in 200 body, connection error RuntimeError, empty list, timeout RuntimeError, 429 retry), TestUpsertMacro, TestCheckGaps (monthly true, large gap false, single true, exactly limit true), TestIngestMacro (normal populates, incremental delta, rerun no duplicate, http error abort gate, missing key before request, non-numeric abort). Mocked requests.
- test_monte_carlo.py (10): output row count = paths*horizon, columns, breach_flag 0/1, breach matches threshold logic, zero volatility identical paths, runtime <120s for 10k x 30, weights renormalise warning, single ticker, missing ticker raises, empty raises.
- test_prophet_forecast.py (16): Layer1 unit tests on fit_and_forecast with synthetic equity/crypto series (500 rows): exactly horizon rows, excludes training history, no NaN, bounds ordering, missing column raises, NaN raises, custom horizon, thin 60 rows still valid. Layer2 pipeline: seeded_db with 600 rows equity/crypto and 50 thin, tests forecast_date today, exactly horizon rows per ticker, thin skipped, no NaN bounds hold, rerun same day idempotent.

Evidence they pass: Our venv run shows 98 passed, 0 failed. No CI badge or coverage report in repo.

APIs: No REST API. Data ingestion uses external APIs: Yahoo Finance via yfinance (no key), FRED via requests with API key from .env. Internal functions are Python modules, not HTTP endpoints. FRED API setup documented in `docs/fred_api_setup.md`.

CI/CD: Absent. No .github/workflows, no .gitlab-ci, no Jenkinsfile, no tox, no pre-commit config beyond sample hooks. GitHub Actions not evidenced.

Containers: Absent. No Dockerfile, docker-compose.yml, no container registry.

Architecture patterns: Modular pipeline with separation of concerns: config central, models pure, scripts orchestration, tests mocked. Idempotent upserts via INSERT OR REPLACE, incremental fetch via last stored date +1, abort gates (MIN_TICKERS_REQUIRED, all FRED series required), single source of truth for crypto classification via config.ASSET_CLASS (refactored in commits 782e25c, 3d92a3c to fix previous suffix-based check). Transaction handling with BEGIN, rollback on exception, extended timeout 30s, user-friendly lock message. Logging via logging module. Pure functions for testability. No dependency injection framework.

Data validation: In ingest_prices: checks df.empty, required columns, MIN_ROWS_PER_TICKER warning, abort gate. In ingest_macro: drops '.' and non-numeric, checks gaps > MAX_MACRO_GAP_DAYS with warning, abort gate on any series failure. In risk_metrics: empty series raises ValueError, combined_risk_score validates [0,1] and weights sum to 1. In forecast: checks required cols, NaN in y raises, MIN_ROWS_FOR_FORECAST skip, staleness warning >3 days, fallback changepoint_prior_scale with warning. In monte_carlo: validates empty returns_df, empty weights, n_paths/horizon positive, weight sum positive, renormalise warning, missing columns raises, overlapping dates check.

Error handling: Comprehensive. Ingest_prices catches generic Exception in _download_ticker returning None, logs warning, continues other tickers. Ingest_macro handles 400 ValueError, 401/403 PermissionError, 429 with 60s sleep retry, 5xx retry with backoff, ConnectionError/Timeout with retry then RuntimeError, JSON parse error. compute_risk handles SQLite locked error via _raise_if_locked converting to user-friendly message about DB Browser, Jupyter, .db-journal. run_forecasts per-ticker try/except logs and continues.

Monitoring: Absent. No Prometheus, Grafana, logging aggregation, alerting. Only print and logging.info statements in scripts.

Security: FRED API key via .env, .env gitignored, .env.example template. No secrets committed. No authentication/authorization (local SQLite). No SQL injection (uses parameterized queries). No PII. Security notes in fred_api_setup.md.

Scale

Rows/files/users/models/endpoints/etc.

Only include numbers supported by repository evidence.

- Tickers: 11 fixed in config.py (AAPL, MSFT, GOOGL, AMZN, JPM, SPY, QQQ, TLT, GLD, BTC-USD, ETH-USD).
- FRED series: 5 in config.py (FEDFUNDS, CPIAUCSL, UNRATE, DGS10, VIXCLS).
- Tables: 6 SQLite tables.
- Tests: 98 tests (verified via pytest).
- Notebooks: 5 files, only 1 substantive (03_prophet_tuning.ipynb 875 lines, outputs show 6 tickers x 10 cps = 60 fits).
- Scripts: 6 scripts (init_db 86 lines, ingest_prices 213, ingest_macro 314, compute_risk 467, run_forecasts 191, verify_acceptance_criteria 181).
- Models: 3 modules (risk_metrics 143 lines, forecast 86, simulation 159).
- Assets: 5 PNGs (architecture 92K, overview 106K, risk 130K, forecast 68K, scenario 115K).
- Dashboard: 1 .pbix 7.7M.
- Config thresholds: MIN_ROWS_PER_TICKER 1000, MIN_TICKERS_REQUIRED 5, MIN_ROWS_FOR_FORECAST 200, FORECAST_HORIZON_DAYS 30, MONTE_CARLO_PATHS 10000, MAX_MACRO_GAP_DAYS 35.
- Data rows: Cannot determine without DB; notebook log says 1629 rows per equity/etf (2020-01-02 to 2026-06-26) and 2370 rows per crypto (2020-01-01 to 2026-06-27) for full load from PRICE_START_DATE, per notebook 03 output. This is plausible for ~6.5 years daily data.
- No users, no endpoints, no models artifacts (no .pkl).

Outcome

What actually worked?

Technical output verified:

- Database initialization creates 6 tables with correct PKs (code verified).
- Price ingestion with incremental logic, upsert, abort gate — proven by 19 tests passing, including mock verification of delta fetch.
- Macro ingestion with robust error handling (400,401,429,5xx, timeout, connection) — proven by 31 tests.
- Risk metrics pure functions correct per known-value tests, handles all-null edge case, validates bounds — proven by 22 tests.
- Monte Carlo vectorized simulation completes 10k x 30 in <120s (test_runtime_under_budget passed in 4.5s in our run), zero-volatility identical paths, breach flag logic — proven by 10 tests.
- Prophet wrapper returns exactly horizon rows, no NaN, bounds ordering, input validation — proven by 16 tests.
- Full pipeline orchestration (compute_returns, compute_risk_scores, run_monte_carlo, run_forecasts) with per-ticker skip, staleness warning, idempotent rerun — proven by pipeline tests.
- Acceptance criteria script checks combined_risk_score in [0,1], no NaN after warmup, CVaR <= VaR, forecast bounds.
- Tuning notebook documents MAPE per asset class with U-shape verification, values applied to config.
- Power BI .pbix file exists and screenshots show 4 pages working at time of capture (dashboard_overview, risk, forecast, scenario). Architecture diagram exists.

Measurable result: 98/98 tests passing offline. Notebook reports mean MAPE 5.69% equity, 3.18% etf, 16.15% crypto on CV. No live DB to show row counts, but code paths are exercised.

Separate technical output from real-world/product impact: No evidence of real-world usage, no users, no deployment, no business impact metrics. Project is educational/portfolio, not production. README states Released v1.0.0 July 2026 but no deployment URL.

Limitations

What does NOT work?

- No database file in repo (gitignored) and `database/` folder missing locally — cannot run pipeline without first running init_db and having API keys + internet.
- `raw_macro` not wired into any risk calculation or dashboard visual — README and STRUCTURE explicitly call this out. Table is populated but unused downstream.
- Scenario Explorer sliders are DAX-only approximation, not re-simulation — README and data_refresh_workflow.md document this. Fan chart does not respond to sliders.
- Live data absent — manual batch only, no scheduler.
- 4 of 5 notebooks are empty stubs (01_data_exploration 17 lines empty markdown, 02,04,05 0 bytes) — STRUCTURE.md notes they are stubs, suggests deleting before v1.0.0 but they remain. Indicates abandoned exploratory work.
- Fixed asset universe — no UI to add tickers without editing config.py.
- Prophet forecasts equities/ETFs on business days vs crypto calendar days, so 30 rows covers different date ranges — documented as not bug but limitation.
- No CI/CD, no Docker, no API, no monitoring.

What is unfinished?

- Macro integration into risk model (listed as potential extension).
- Live/scheduled refresh (potential extension).
- Streamlit UI (potential extension).
- Additional asset classes (potential extension).
- Notebook cleanup (4 stubs).

What would I change?

Include:

- modelling weaknesses: No baseline comparison, no holdout evaluation for final forecasts, tuning only on 2 tickers per class (6 of 11), MAPE on crypto ~16-18% is high, suggests Prophet may be poor for crypto; no exogenous features; combined_risk_score uses equal weighting with no empirical justification; VaR/CVaR rolling window 252 may be too short for tail estimation; annualisation factor fixed 252/365 ignores actual trading calendar variations.
- architecture weaknesses: No abstraction for data source (yfinance hard-coded), no config validation, no dependency injection, SQLite single-writer lock risk (mitigated with timeout but not solved), no separation of raw vs processed DB, no model versioning, no artifact storage.
- reproducibility problems: Requires FRED API key, yfinance network, Prophet (heavy dependency with cmdstan), Power BI Desktop + ODBC driver (Windows-only), no lockfile (requirements.txt no versions), no Python version pinned, database not included so cannot reproduce dashboard without full ingestion.
- broken/dead integrations: raw_macro ingestion works but downstream dead; Power BI cannot be verified in Linux environment; schema_diagram.md empty (0 bytes) in checkout despite README referencing it — doc missing.
- deployment issues: No deployment, local only, manual steps, no error notification, no idempotency across processes (SQLite lock).
- technical debt: 4 empty notebooks, commented pip install lines in notebook, suppress_stan_output hack, print statements mixed with logging, sys.path.insert hack in verify_acceptance_criteria.py, __pycache__ committed? Actually gitignored but present locally after tests.
- unsupported claims: README says “one Refresh click away” but requires SQLite ODBC driver setup not trivial; “ML-driven risk metrics” — risk metrics are statistical not ML except Prophet; “10,000-path Monte Carlo” — true but historical bootstrap is simple, not advanced; architecture diagram shows FRED -> ETL -> SQLite -> ML Models -> Power BI but FRED path is dead.

Current repository status

Runs locally: Partially verified. `scripts/init_db.py` would create DB (code verified), `ingest_prices` and `ingest_macro` require network and API key — not tested live, but unit tests mock and pass. `compute_risk` and `run_forecasts` require DB populated — logic verified via tests but not end-to-end without DB. Power BI refresh cannot be verified without Power BI Desktop and ODBC driver. Overall, pipeline is runnable in theory per README quickstart, but not verified end-to-end in this environment due to missing DB and external dependencies.

Tests pass: Yes — 98 tests passing when run with Python 3.11 venv including prophet, yfinance, etc. Verified via two pytest runs (72 + 26). No CI to prove historical pass, but local pass confirmed.

Deployment: None. No Dockerfile, no cloud config, no Power BI Service. Local-only.

README quality: High — 206 lines, includes problem statement, architecture diagram reference, tech stack table, quickstart with 6 steps, verify install, schema table, data refresh workflow summary, dashboard description with 4 screenshots, known limitations (5 bullets) and potential extensions (4 bullets), project status v1.0.0 July 2026. Honest about limitations (macro not wired, scenario approximation, not live). STRUCTURE.md also high quality (190 lines) documenting every folder/file and noting stub notebooks.

Demo available: Screenshots in `assets/` (4 dashboard pages + architecture). No live demo URL, no video, no Streamlit. .pbix file exists but requires Power BI Desktop to view — not web demo.

Evidence

Relevant files:

- `config.py` — central config, 91 lines, defines TICKERS, ASSET_CLASS, FRED_SERIES, thresholds.
- `scripts/init_db.py` — SCHEMA_SQL 6 tables, init_db function.
- `scripts/ingest_prices.py` — 213 lines, _fetch_window, _download_ticker, _upsert_prices, ingest_prices.
- `scripts/ingest_macro.py` — 314 lines, _require_api_key, _fetch_observations with retry logic, _check_gaps.
- `models/risk_metrics.py` — 143 lines, 6 pure functions.
- `models/monte_carlo/simulation.py` — 159 lines, simulate vectorized.
- `models/prophet/forecast.py` — 86 lines, fit_and_forecast.
- `scripts/compute_risk.py` — 467 lines, compute_returns, compute_risk_scores, run_monte_carlo, _is_crypto_ticker uses ASSET_CLASS.
- `scripts/run_forecasts.py` — 191 lines, run_forecasts, _changepoint_prior_scale_for.
- `scripts/verify_acceptance_criteria.py` — 181 lines, verify_issue_3 and verify_issue_5 checks.
- `tests/test_risk_metrics.py` — 22 tests, known-value.
- `tests/test_ingest_prices.py` — 19 tests, mocked yfinance.
- `tests/test_ingest_macro.py` — 31 tests, mocked requests.
- `tests/test_monte_carlo.py` — 10 tests, runtime budget.
- `tests/test_prophet_forecast.py` — 16 tests, synthetic data + pipeline.
- `notebooks/03_prophet_tuning.ipynb` — 875 lines, CV grid search with outputs showing MAPE table and best values.
- `notebooks/01_data_exploration.ipynb` — 17 lines empty, stub.
- `notebooks/02_risk_metrics_dev.ipynb`, `04_monte_carlo_analysis.ipynb`, `05_dashboard_data_validation.ipynb` — 0 bytes, stubs.
- `dashboard/financial_risk_monitor.pbix` — 7.7M binary.
- `assets/architecture_diagram.png` (92K), `dashboard_overview.png` (106K), `dashboard_risk.png` (130K), `dashboard_forecast.png` (68K), `dashboard_scenario.png` (115K).
- `docs/data_refresh_workflow.md` — 129 lines, detailed refresh steps, DAX measure.
- `docs/fred_api_setup.md` — 43 lines, API key setup.
- `docs/schema_diagram.md` — 0 bytes (empty) in checkout, but README references it.
- `requirements.txt` — 15 lines, dependencies.
- `.env.example`, `.gitignore`.

PRs:

- #1 Project scaffold, environment setup, and database initialisation — CLOSED 2026-06-27
- #2 Implement price and macro data ingestion — CLOSED 2026-06-27
- #3 Build the core risk metrics module — CLOSED 2026-07-07
- #4 Implement Monte Carlo portfolio simulation — CLOSED 2026-07-07
- #5 Build the Prophet forecasting pipeline — CLOSED 2026-07-09
- #6 Build the Power BI dashboard (.pbix) — CLOSED 2026-07-13
- #7 Testing, documentation, and repository polish — CLOSED 2026-07-22 (PR #14 testing-polish)
- Additional PRs #8-#14 listed in git log: db-initialisation, data-ingestion, risk-metrics, monte-carlo, prophet-forecast, dashboard-build, testing-polish.

Issues:

- 7 closed issues mirroring PRs, per `gh issue list` (CLOSED #1 scaffold, #2 ingestion, #3 risk metrics, #4 Monte Carlo, #5 Prophet, #6 dashboard, #7 testing polish).

Screenshots:

- `assets/dashboard_overview.png` — Portfolio Overview risk heatmap, sparklines, cards.
- `assets/dashboard_risk.png` — Rolling volatility, drawdown, VaR/CVaR bars.
- `assets/dashboard_forecast.png` — Actual vs predicted with confidence band.
- `assets/dashboard_scenario.png` — Scenario Explorer sliders, Adjusted Risk Score, Monte Carlo fan chart.
- `assets/architecture_diagram.png` — Pipeline diagram.

Demo:

- No live web demo. Local Power BI .pbix requires Desktop + SQLite ODBC.

Presentation:

- None evidenced.

Candidate CV bullets

Leave this section blank.

Work required

Concrete remaining tasks only.

Critical

Problems that prevent the repository from being credible professional evidence.

- Populate `database/` folder or document that DB is gitignored and provide sample DB or script to generate minimal demo DB — currently repo has no DB, so end-to-end cannot be verified without API keys. Add `database/README.md` or provide `scripts/seed_demo_db.py` that creates synthetic data for testing.
- Fill or remove 4 empty notebook stubs (01,02,04,05) — currently imply exploratory work that didn't happen; STRUCTURE.md already flags this. Delete or implement.
- Fix `docs/schema_diagram.md` — currently 0 bytes empty, but README and STRUCTURE reference it as containing ER diagram. Either populate or remove reference.
- Pin dependencies in `requirements.txt` with versions (currently unpinned) and add Python version (e.g., python 3.11) to ensure reproducibility — current file lists packages without versions, prophet is notoriously version-sensitive.
- Add evidence that Power BI dashboard actually connects to SQLite — e.g., screenshot of data source settings, or DAX measures file, or documentation of ODBC setup steps beyond docs. Currently only screenshots prove visuals, not data connectivity.

High value

Changes that materially increase the strength of the engineering evidence.

- Add CI workflow (`.github/workflows/ci.yml`) running pytest on push — would prove tests pass historically, not just locally. Currently 98 tests passing locally but no CI badge.
- Add Dockerfile or devcontainer for reproducible environment — prophet + yfinance + ODBC driver setup is non-trivial; container would lower barrier.
- Wire `raw_macro` into risk model or dashboard — currently dead code path; implementing even simple overlay (e.g., flag risk scores during rate hikes) would turn ingestion from placeholder into used feature.
- Add final forecast evaluation: backtest script that compares old forecasts (forecast_date) vs actual prices, computes MAPE on holdout, logs to file — would turn tuning notebook into validated model.
- Add data validation tests for `verify_acceptance_criteria.py` in CI and document its output — currently script exists but not integrated.
- Add model artifact versioning or at least save Prophet models or forecast outputs as CSV in `data/processed/` for audit.
- Improve error handling for SQLite locked scenario with retry or WAL mode — currently just raises friendly error.

Optional

Polish that is useful but not necessary.

- Add Streamlit UI as mentioned in README potential extensions — would provide web demo without Power BI license.
- Add cron example or Task Scheduler script for scheduled refresh.
- Add coverage report (pytest-cov) and badge.
- Add pre-commit hooks (black, ruff) — currently none.
- Add LICENSE file.
- Compress or document Power BI file size (7.7M) and add .pbix version info.
- Add additional asset classes (commodities, bonds) as extension.
- Add logging to file, not just console.

Professional Evidence Assessment

1. What engineering capability does this project prove best?

Batch ETL pipeline engineering with robust data ingestion: incremental fetch via last stored date, idempotent upserts (INSERT OR REPLACE), abort gates (MIN_TICKERS_REQUIRED, all FRED series required), comprehensive error handling for external APIs (400,401,429,5xx, timeout, connection, '.' missing values), SQLite transaction handling with extended timeout and user-friendly lock messages, modular separation (config central, models pure, scripts orchestration), and thorough unit testing with mocking (98 tests covering normal, error, upsert, abort, edge cases). The ingestion and risk computation code is production-grade in error handling and testability, despite lacking CI/CD or containers.

2. What ML/AI capability does it prove best?

Applied time series forecasting with Prophet: proper handling of business vs calendar day frequency (B for equities/ETFs, D for crypto), per-asset-class hyperparameter tuning via cross-validation (rolling-origin CV, MAPE to avoid scale bias, log-scale grid, U-shape verification to ensure optimum not at edge), and integration into batch pipeline with staleness checks and fallback logic. Also demonstrates statistical risk modelling (historical VaR/CVaR, Monte Carlo bootstrap preserving fat tails, vectorized implementation meeting runtime budget). Not deep learning, but solid applied financial ML with honest documentation of limitations.

3. What is the strongest verifiable achievement?

The 98 unit tests all passing offline with mocked external dependencies, covering pure risk metrics (known-value assertions), ingestion (incremental, upsert, abort gates, HTTP error handling), Monte Carlo (row count, breach flag, zero-volatility, runtime budget <120s for 10k x 30), and Prophet (horizon rows, bounds ordering, thin ticker skip, idempotent rerun). Combined with the substantive tuning notebook (03_prophet_tuning.ipynb) that documents a full CV grid search across 6 tickers x 10 cps values with MAPE results and rationale for chosen values (equity 0.5, etf 0.1, crypto 2.0). This shows both engineering discipline and ML methodology.

4. What is the biggest credibility weakness?

The Power BI dashboard is the claimed final deliverable but cannot be independently verified without Power BI Desktop and ODBC driver, and its data connectivity is only implied via screenshots. Additionally, `raw_macro` is ingested but dead (not used downstream), Scenario Explorer is DAX approximation not re-simulation, and 4 of 5 notebooks are empty stubs, which undermines the claim of extensive exploration. The lack of a database file (gitignored) means end-to-end reproducibility requires API keys and network, and `docs/schema_diagram.md` is empty despite being referenced.

5. Is there enough here to justify investing additional time in this project?

Yes, conditionally. The core pipeline (ingestion, risk metrics, Monte Carlo, Prophet) is well-engineered and well-tested, with honest documentation of limitations. The foundation is solid. High-value investments would be: adding CI, wiring macro data into risk model, adding final forecast backtest evaluation, and cleaning up stubs/docs. If the goal is Applied AI/ML Engineer portfolio, the project already demonstrates strong data engineering and applied modelling; polishing the dead paths and adding a web demo (Streamlit) would make it significantly stronger without major rewrite. Not worth rebuilding from scratch, but worth 1-2 weeks of targeted improvements.

6. What type of professional role would this project support as evidence?

Data Engineer (batch ETL, SQLite, incremental loads, error handling), Analytics Engineer (risk metrics, Power BI, data refresh workflow), Applied ML Engineer / Financial Data Scientist (Prophet forecasting with CV tuning, Monte Carlo simulation, risk metrics), Python Backend Engineer (modular Python, testing with pytest and mocking). Less suitable for MLOps (no CI/CD, containers, model registry), Data Scientist research (no baseline, no holdout evaluation), or Frontend Engineer (no web UI). Best fit: Applied AI/ML Engineer or Financial Analytics Engineer roles requiring end-to-end pipeline from API ingestion to BI delivery.

7. What claims should I NOT make publicly based on the current repository?

Do NOT claim: live/real-time risk monitoring (it's manual batch, README says not live); macro indicators drive risk scores (README says raw_macro not wired); Scenario Explorer re-runs Monte Carlo under shocks (README says DAX approximation only, fan chart not scenario-responsive); Power BI dashboard is deployed or accessible via Service/gateway (it's Desktop only, local .pbix); model achieves X% accuracy in production (only CV MAPE on 2 tickers per class, no holdout test, crypto MAPE 16% high); pipeline is production-deployed with scheduling/monitoring (no scheduler, no monitoring, no CI/CD, no Docker); extensive exploratory analysis in notebooks (4 of 5 are empty stubs); database included or reproducible without API keys (DB gitignored, requires FRED key and yfinance network). Also do NOT claim team leadership or solo ownership unless you can prove you are Tessa-Saumu — git history shows Tessa-Saumu as primary author but authorship linking to portfolio candidate cannot be proven from repo alone.

