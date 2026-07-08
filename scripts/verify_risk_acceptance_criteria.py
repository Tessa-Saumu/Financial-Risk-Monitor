"""
verify_risk_acceptance_criteria.py — checks the Issue 3 & Issue 5 acceptance criteria
against whatever is currently in the real database. 

Usage:
    python -m scripts.verify_risk_acceptance_criteria              # Runs all checks
    python -m scripts.verify_risk_acceptance_criteria --issue 3    # Runs only Issue 3 checks
    python -m scripts.verify_risk_acceptance_criteria --issue 5    # Runs only Issue 5 checks
"""
import argparse
import os
import sqlite3
import sys

import pandas as pd

# Allow `python scripts/verify_risk_acceptance_criteria.py` to find config.py at
# the project root, the same way compute_risk.py needs to be run as
# `python -m scripts.compute_risk` (or with the root on PYTHONPATH) to find
# it. This makes the direct-file invocation work too, since that's the more
# natural thing to type.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import DB_PATH


def verify_issue_3(conn):
    failures = []
    
    # ── Criterion: risk_scores.combined_risk_score in [0, 1] for all rows ──
    rs = pd.read_sql("SELECT date, ticker, combined_risk_score FROM risk_scores", conn)
    non_null = rs.dropna(subset=["combined_risk_score"])

    if non_null.empty:
        failures.append("combined_risk_score: no non-null rows found at all — "
                         "did compute_risk_scores() actually run?")
    else:
        out_of_bounds = non_null[
            (non_null["combined_risk_score"] < 0) | (non_null["combined_risk_score"] > 1)
        ]
        if len(out_of_bounds) > 0:
            failures.append(
                f"combined_risk_score: {len(out_of_bounds)} row(s) OUT OF [0,1] range. "
                f"Examples:\n{out_of_bounds.head(5).to_string(index=False)}"
            )
        else:
            print(f"✓ combined_risk_score in [0,1] for all {len(non_null)} non-null rows "
                  f"(range: {non_null['combined_risk_score'].min():.4f} – "
                  f"{non_null['combined_risk_score'].max():.4f})")

        null_count = len(rs) - len(non_null)
        if null_count > 0:
            print(f"  (note: {null_count} row(s) have NULL combined_risk_score — "
                  f"expected during each ticker's warm-up period, worth a quick look "
                  f"if this number seems too high)")

    # ── Criterion: no NaN in asset_returns after the rolling warm-up period ──
    ar = pd.read_sql(
        "SELECT date, ticker, daily_return, rolling_7d_vol, rolling_30d_vol, drawdown "
        "FROM asset_returns ORDER BY ticker, date",
        conn,
    )
    if ar.empty:
        failures.append("asset_returns: table is empty — did compute_returns() run?")
    else:
        bad_rows = []
        for ticker, g in ar.groupby("ticker"):
            g = g.reset_index(drop=True)
            # rolling_30d_vol has the longest warm-up (30 periods) of the four
            # columns, so that's the point after which NOTHING should be NaN.
            post_warmup = g.iloc[30:]
            nan_mask = post_warmup[
                ["daily_return", "rolling_7d_vol", "rolling_30d_vol", "drawdown"]
            ].isna().any(axis=1)
            if nan_mask.any():
                bad_rows.append((ticker, int(nan_mask.sum())))

        if bad_rows:
            failures.append(
                f"asset_returns: NaN values found after the 30-day warm-up period "
                f"in {len(bad_rows)} ticker(s): {bad_rows}"
            )
        else:
            print(f"✓ No NaN values in asset_returns after the 30-day warm-up period "
                  f"(checked {ar['ticker'].nunique()} tickers, {len(ar)} total rows)")

    # ── Bonus sanity check the issue implies but doesn't spell out: CVaR <= VaR ──
    rs_full = pd.read_sql("SELECT date, ticker, var_95, cvar_95 FROM risk_scores", conn).dropna()
    if not rs_full.empty:
        violations = rs_full[rs_full["cvar_95"] > rs_full["var_95"]]
        if len(violations) > 0:
            failures.append(
                f"cvar_95 > var_95 in {len(violations)} row(s) — CVaR should always be "
                f"at least as far into the loss tail as VaR. Examples:\n"
                f"{violations.head(5).to_string(index=False)}"
            )
        else:
            print(f"✓ cvar_95 <= var_95 holds for all {len(rs_full)} non-null rows")

    return failures

def verify_issue_5(conn):
    failures = []
    
    # ── Criterion: lower_bound <= predicted_close <= upper_bound in forecasts ──
    try:
        # Updated to match the actual columns in your database screenshot
        fc = pd.read_sql("SELECT date, ticker, lower_bound, predicted_close, upper_bound FROM forecasts", conn)
        
        if fc.empty:
            failures.append("forecasts: table is empty — did the forecast generation run?")
        else:
            # Drop rows where any of the forecast components are null
            non_null_fc = fc.dropna(subset=["lower_bound", "predicted_close", "upper_bound"])
            
            if non_null_fc.empty:
                failures.append("forecasts: no non-null forecast rows found at all.")
            else:
                out_of_bounds_fc = non_null_fc[
                    (non_null_fc["predicted_close"] < non_null_fc["lower_bound"]) | 
                    (non_null_fc["predicted_close"] > non_null_fc["upper_bound"])
                ]
                
                if len(out_of_bounds_fc) > 0:
                    failures.append(
                        f"forecasts: {len(out_of_bounds_fc)} row(s) violate lower_bound <= predicted_close <= upper_bound. "
                        f"Examples:\n{out_of_bounds_fc.head(5).to_string(index=False)}"
                    )
                else:
                    print(f"✓ lower_bound <= predicted_close <= upper_bound holds for all {len(non_null_fc)} "
                          f"non-null rows in the forecasts table.")

                null_count_fc = len(fc) - len(non_null_fc)
                if null_count_fc > 0:
                    print(f"  (note: {null_count_fc} row(s) have NULL forecast values)")
                    
    except pd.errors.DatabaseError as e:
        # Better error logging to show exactly what went wrong if it fails again
        failures.append(f"forecasts: Database error occurred (check table and column names): {e}")
        
    return failures


def main():
    parser = argparse.ArgumentParser(description="Verify database criteria for specific issues.")
    parser.add_argument(
        "--issue", 
        type=int, 
        choices=[3, 5], 
        help="Specify which issue criteria to verify (3 or 5). If omitted, verifies all."
    )
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    all_failures = []

    # Run Issue 3
    if args.issue in [None, 3]:
        print("─── Verifying Issue 3 ───")
        all_failures.extend(verify_issue_3(conn))
        print()

    # Run Issue 5
    if args.issue in [None, 5]:
        print("─── Verifying Issue 5 ───")
        all_failures.extend(verify_issue_5(conn))
        print()

    conn.close()

    if all_failures:
        print("FAILED — issue(s) are not ready to close:")
        for f in all_failures:
            print(f"  ✗ {f}")
        sys.exit(1)
    else:
        print("All requested acceptance criteria PASSED against the live database.")


if __name__ == "__main__":
    main()