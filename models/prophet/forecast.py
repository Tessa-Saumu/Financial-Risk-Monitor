"""
forecast.py — helper functions for fitting Prophet models and
generating forward-looking price forecasts with confidence intervals.
Called by scripts/run_forecasts.py.
"""
import logging

import pandas as pd
from prophet import Prophet

# cmdstanpy (Prophet's fitting backend) logs an INFO line per fit by
# default. Across 11 tickers that drowns out the per-ticker progress
# logging in run_forecasts.py, so it's quieted here at import time. This
# does NOT suppress cmdstanpy's own stdout compiler/optimizer chatter on
# first use — that's a separate cmdstan quirk, harmless, and only shows
# up once per environment.
logging.getLogger("cmdstanpy").setLevel(logging.WARNING)


def fit_and_forecast(
    df: pd.DataFrame,
    horizon: int = 30,
    changepoint_prior_scale: float = 0.05,
    freq: str = "D",
    interval_width: float = 0.95,
) -> pd.DataFrame:
    """
    Fit a Prophet model on a single asset's price history
    and return a forecast DataFrame with ds, yhat, yhat_lower, yhat_upper.

    Args:
        df: DataFrame with columns ['ds', 'y'] (date and close price).
            'ds' must be datetime64 (or something pd.to_datetime can
            already parse); 'y' is the value being forecast — here,
            close price. Prophet is univariate: 'ds' is not a predictive
            feature in the usual ML sense, it's the calendar timestamp
            that trend/seasonality/holiday components are functions of.
        horizon: number of periods to forecast forward, at the given
            `freq`. Always returns exactly `horizon` rows — this is
            forecast-only output (include_history=False), it does not
            include the training history.
        changepoint_prior_scale: trend flexibility. Prophet's default is
            0.05; pass the asset-class-tuned value from
            notebooks/03_prophet_tuning.ipynb rather than relying on the
            default for real forecasts.
        freq: pandas frequency string for future_dataframe generation.
            'B' (business day) for tickers with weekday-only trading
            history (equities/ETFs) — 'D' would otherwise ask Prophet to
            predict prices for days it never saw a trading session on,
            which Prophet's own docs flag as producing unidentifiable,
            overfit seasonality for those days. 'D' (calendar day) for
            24/7 tickers (crypto) where every calendar day has real
            training data.
        interval_width: width of the yhat_lower/yhat_upper band. Prophet
            defaults to 0.80; must be passed explicitly for 95% bounds.

    Returns:
        DataFrame with columns ['ds', 'yhat', 'yhat_lower', 'yhat_upper'],
        exactly `horizon` rows, sorted by ds ascending.
    """
    required_cols = {"ds", "y"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"fit_and_forecast: input df missing required column(s): {missing}")

    if df["y"].isna().any():
        raise ValueError(
            "fit_and_forecast: input 'y' contains NaN values — clean or "
            "drop them before fitting (Prophet will silently fit on "
            "whatever remains, which can distort the trend)."
        )

    model = Prophet(
        daily_seasonality=False,   # price data is daily-resolution, not intraday
        weekly_seasonality=True,
        yearly_seasonality=True,
        changepoint_prior_scale=changepoint_prior_scale,
        interval_width=interval_width,
    )
    model.add_country_holidays(country_name="US")
    model.fit(df[["ds", "y"]])

    future = model.make_future_dataframe(periods=horizon, freq=freq, include_history=False)
    forecast = model.predict(future)

    return forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]].sort_values("ds").reset_index(drop=True)