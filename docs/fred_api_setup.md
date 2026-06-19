# FRED API Setup

## Overview

This project uses the Federal Reserve Economic Data (FRED) API to retrieve macroeconomic and financial time-series data.

## Creating a FRED API Key

1. Create or log in to your FRED account.

2. Navigate to:
   https://fred.stlouisfed.org/docs/api/api_key.html

3. Select **"Request or view your API keys"**.

4. When prompted to describe your application, provide a brief description of the project. Example:

   > An end-to-end financial analytics pipeline that ingests market and macroeconomic data, computes ML-driven risk metrics, runs Monte Carlo portfolio simulations, and serves a refreshable multi-page Power BI dashboard.

5. Submit the form.

6. FRED will generate and display an API key.

## Environment Configuration

Add the API key to your `.env` file:

```env
FRED_API_KEY=your_api_key_here
```

## Security Notes

* Never commit API keys to version control.
* Ensure `.env` is included in `.gitignore`.
* Share API keys only through approved secure channels.

## Verification

You can verify that the API key is configured correctly by running the project's data ingestion scripts or by making a test request to the FRED API.

If the API key is valid, the API should return the requested economic data without authentication errors.
