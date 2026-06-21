"""Placeholder script for downloading price and volume data.

Expected inputs:
- Ticker universe
- Date window
- Benchmark ticker for abnormal return calculations

Expected outputs:
- Daily OHLCV files in `data/raw/`
- Optional cleaned daily panel in `data/interim/`
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch daily price data for project tickers.")
    parser.add_argument("--source", default="yfinance", help="Price source identifier.")
    parser.add_argument("--start-date", help="Start date in YYYY-MM-DD format.")
    parser.add_argument("--end-date", help="End date in YYYY-MM-DD format.")
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=[],
        help="List of tickers to download.",
    )
    parser.add_argument("--benchmark", default="SPY", help="Benchmark ticker.")
    parser.add_argument(
        "--output",
        default="data/raw/prices_raw.csv",
        help="Relative output path for downloaded prices.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    output_path = Path(args.output)

    plan = {
        "status": "placeholder",
        "source": args.source,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "tickers": args.tickers,
        "benchmark": args.benchmark,
        "output": str(output_path),
        "todo": [
            "Download adjusted daily prices and volume.",
            "Store benchmark series needed for simple abnormal return construction.",
            "Check missing dates, ticker changes, and split-adjustment behavior.",
            "Export a tidy daily panel for later event matching.",
        ],
    }

    print(json.dumps(plan, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
