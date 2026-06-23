"""Build daily returns and abnormal returns from raw daily price data."""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from utils import ensure_dir, resolve_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build daily returns and benchmark-adjusted returns.")
    parser.add_argument(
        "--input",
        default="data/raw/prices/yfinance_daily_prices.csv",
        help="Input raw daily price CSV.",
    )
    parser.add_argument(
        "--output",
        default="data/interim/daily_returns.csv",
        help="Output CSV for daily returns.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    input_path = resolve_path(args.input)
    output_path = resolve_path(args.output)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    df = pd.read_csv(input_path)
    required_columns = ["ticker", "date", "adj_close"]
    missing = [column for column in required_columns if column not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df["date"] = pd.to_datetime(df["date"])
    numeric_columns = ["open", "high", "low", "close", "adj_close", "volume"]
    for column in numeric_columns:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")

    df = df.sort_values(["ticker", "date"]).reset_index(drop=True)
    df["simple_return"] = df.groupby("ticker")["adj_close"].pct_change()
    df["log_return"] = df.groupby("ticker")["adj_close"].transform(
        lambda series: np.log(series / series.shift(1))
    )

    benchmark_returns = (
        df.loc[df["ticker"].isin(["SPY", "QQQ"]), ["ticker", "date", "simple_return"]]
        .pivot(index="date", columns="ticker", values="simple_return")
        .rename(columns={"SPY": "spy_return", "QQQ": "qqq_return"})
        .reset_index()
    )

    df = df.merge(benchmark_returns, on="date", how="left")
    df["abret_spy"] = df["simple_return"] - df["spy_return"]
    df["abret_qqq"] = df["simple_return"] - df["qqq_return"]
    df["date"] = df["date"].dt.date

    ensure_dir(output_path.parent)
    df.to_csv(output_path, index=False)

    print("Daily returns build completed.")
    print(f"Input: {input_path}")
    print(f"Output: {output_path}")
    print(f"Rows written: {len(df):,}")
    print("\nTicker coverage:")
    print(df["ticker"].value_counts().sort_index().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
