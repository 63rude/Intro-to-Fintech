"""Fetch daily price data for the project ticker universe using yfinance."""

from __future__ import annotations

import argparse
from datetime import timedelta
from pathlib import Path

import pandas as pd

from utils import ensure_dir, load_ticker_config, resolve_path


CLASSIFICATION_DEFAULT = (
    "data/processed/llm_output/llm_classifications_sample_n50_per_stratum_max1500_final.csv"
)
BENCHMARK_TICKERS = ["SPY", "QQQ"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch daily adjusted price data from yfinance.")
    parser.add_argument(
        "--config",
        default="config/competitor_groups.yaml",
        help="Competitor group configuration file.",
    )
    parser.add_argument(
        "--classifications",
        default=CLASSIFICATION_DEFAULT,
        help="LLM classification file used to infer the date window.",
    )
    parser.add_argument(
        "--start-date",
        default="",
        help="Optional explicit start date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--end-date",
        default="",
        help="Optional explicit end date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--output",
        default="data/raw/prices/yfinance_daily_prices.csv",
        help="Output CSV for daily OHLCV prices.",
    )
    return parser


def get_project_tickers(config: dict) -> list[str]:
    tickers: list[str] = []
    seen: set[str] = set()
    industries = config.get("industries", {})
    for payload in industries.values():
        if not isinstance(payload, dict):
            continue
        for ticker in payload.get("tickers", []):
            ticker_text = str(ticker).strip().upper()
            if ticker_text and ticker_text not in seen:
                seen.add(ticker_text)
                tickers.append(ticker_text)
    for ticker in BENCHMARK_TICKERS:
        if ticker not in seen:
            seen.add(ticker)
            tickers.append(ticker)
    return tickers


def infer_date_window(classifications_path: Path) -> tuple[str, str]:
    df = pd.read_csv(classifications_path, usecols=["published_date"])
    published_dates = pd.to_datetime(df["published_date"], errors="coerce").dropna()
    if published_dates.empty:
        raise ValueError(f"No valid published_date values found in {classifications_path}")

    start_date = (published_dates.min() - timedelta(days=30)).date().isoformat()
    end_date = (published_dates.max() + timedelta(days=10)).date().isoformat()
    return start_date, end_date


def download_prices(tickers: list[str], start_date: str, end_date: str) -> pd.DataFrame:
    try:
        import yfinance as yf
    except ImportError as exc:
        raise ImportError(
            "yfinance is required for fetch_prices.py. Install it with `python -m pip install yfinance`."
        ) from exc

    download_end = (pd.Timestamp(end_date) + pd.Timedelta(days=1)).date().isoformat()
    raw = yf.download(
        tickers=tickers,
        start=start_date,
        end=download_end,
        auto_adjust=False,
        progress=False,
        group_by="ticker",
        threads=True,
    )
    if raw.empty:
        raise ValueError("yfinance returned no price data.")

    frames: list[pd.DataFrame] = []
    for ticker in tickers:
        if isinstance(raw.columns, pd.MultiIndex):
            if ticker not in raw.columns.get_level_values(0):
                continue
            ticker_frame = raw[ticker].copy()
        else:
            ticker_frame = raw.copy()

        if ticker_frame.empty:
            continue

        ticker_frame = ticker_frame.reset_index()
        date_column = ticker_frame.columns[0]
        ticker_frame = ticker_frame.rename(
            columns={
                date_column: "date",
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Adj Close": "adj_close",
                "Volume": "volume",
            }
        )
        if "adj_close" not in ticker_frame.columns:
            ticker_frame["adj_close"] = ticker_frame["close"]

        ticker_frame["ticker"] = ticker
        frames.append(
            ticker_frame[
                ["ticker", "date", "open", "high", "low", "close", "adj_close", "volume"]
            ]
        )

    if not frames:
        raise ValueError("No ticker frames were extracted from the yfinance response.")

    prices = pd.concat(frames, ignore_index=True)
    prices["date"] = pd.to_datetime(prices["date"]).dt.date
    prices = prices.sort_values(["ticker", "date"]).reset_index(drop=True)
    return prices


def main() -> int:
    args = build_parser().parse_args()

    config_path = resolve_path(args.config)
    classifications_path = resolve_path(args.classifications)
    output_path = resolve_path(args.output)

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    if not classifications_path.exists():
        raise FileNotFoundError(f"Classification file not found: {classifications_path}")

    config = load_ticker_config(config_path)
    tickers = get_project_tickers(config)
    inferred_start, inferred_end = infer_date_window(classifications_path)
    start_date = args.start_date or inferred_start
    end_date = args.end_date or inferred_end

    prices = download_prices(tickers, start_date, end_date)
    ensure_dir(output_path.parent)
    prices.to_csv(output_path, index=False)

    print("Price fetch completed.")
    print(f"Tickers fetched: {len(sorted(prices['ticker'].unique()))}")
    print(f"Requested date window: {start_date} to {end_date}")
    print(f"Output: {output_path}")
    print(f"Rows written: {len(prices):,}")
    print("\nRows per ticker:")
    print(prices["ticker"].value_counts().sort_index().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
