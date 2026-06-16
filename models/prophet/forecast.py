"""
forecast.py — helper functions for fitting Prophet models and
generating forward-looking price forecasts with confidence intervals.
Called by scripts/run_forecasts.py.
"""
import pandas as pd
from prophet import Prophet


def fit_and_forecast(df: pd.DataFrame, horizon: int = 30) -> pd.DataFrame:
    """
    Fit a Prophet model on a single asset's price history
    and return a forecast DataFrame with ds, yhat, yhat_lower, yhat_upper.

    Args:
        df: DataFrame with columns ['ds', 'y'] (date and close price)
        horizon: number of days to forecast forward
    """
    # TODO: fit Prophet, call make_future_dataframe, return forecast
    raise NotImplementedError
