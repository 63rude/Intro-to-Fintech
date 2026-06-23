"""Build a competitor event panel from LLM-classified news and daily returns."""

from __future__ import annotations

import argparse
from bisect import bisect_left
from typing import Any

import numpy as np
import pandas as pd

from utils import ensure_dir, load_ticker_config, resolve_path


CLASSIFICATION_DEFAULT = (
    "data/processed/llm_output/llm_classifications_sample_n50_per_stratum_max1500_final.csv"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build an event panel for competitor reactions.")
    parser.add_argument(
        "--news",
        default=CLASSIFICATION_DEFAULT,
        help="Path to labeled news data.",
    )
    parser.add_argument(
        "--links",
        default="data/interim/news_article_ticker_links.csv",
        help="Path to article-to-ticker links.",
    )
    parser.add_argument(
        "--prices",
        default="data/interim/daily_returns.csv",
        help="Path to daily price/return data.",
    )
    parser.add_argument(
        "--config",
        default="config/competitor_groups.yaml",
        help="Competitor group configuration file.",
    )
    parser.add_argument(
        "--output",
        default="data/processed/news_competitor_event_panel.csv",
        help="Output path for the event panel.",
    )
    return parser


def to_bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin(["true", "1", "yes"])


def sum_or_nan(values: list[float]) -> float:
    valid_values = [value for value in values if pd.notna(value)]
    if not valid_values:
        return np.nan
    return float(np.sum(valid_values))


def get_value(pivot: pd.DataFrame, date_value: pd.Timestamp | pd.NaT, ticker: str) -> float:
    if pd.isna(date_value):
        return np.nan
    if date_value not in pivot.index:
        return np.nan
    if ticker not in pivot.columns:
        return np.nan
    return pivot.at[date_value, ticker]


def build_ticker_maps(config: dict[str, Any]) -> tuple[dict[str, str], dict[str, list[str]]]:
    ticker_to_group: dict[str, str] = {}
    group_to_tickers: dict[str, list[str]] = {}
    for group_name, payload in config.get("industries", {}).items():
        if not isinstance(payload, dict):
            continue
        tickers = [str(ticker).strip().upper() for ticker in payload.get("tickers", []) if str(ticker).strip()]
        group_to_tickers[group_name] = tickers
        for ticker in tickers:
            ticker_to_group[ticker] = group_name
    return ticker_to_group, group_to_tickers


def map_to_trading_dates(
    published_dates: pd.Series,
    trading_dates: list[pd.Timestamp],
) -> tuple[list[pd.Timestamp | pd.NaT], list[int | None]]:
    mapped_dates: list[pd.Timestamp | pd.NaT] = []
    mapped_indices: list[int | None] = []
    for date_value in published_dates:
        if pd.isna(date_value):
            mapped_dates.append(pd.NaT)
            mapped_indices.append(None)
            continue
        idx = bisect_left(trading_dates, date_value.normalize())
        if idx >= len(trading_dates):
            mapped_dates.append(pd.NaT)
            mapped_indices.append(None)
            continue
        mapped_dates.append(trading_dates[idx])
        mapped_indices.append(idx)
    return mapped_dates, mapped_indices


def main() -> int:
    args = build_parser().parse_args()

    news_path = resolve_path(args.news)
    links_path = resolve_path(args.links)
    prices_path = resolve_path(args.prices)
    config_path = resolve_path(args.config)
    output_path = resolve_path(args.output)

    for path in [news_path, links_path, prices_path, config_path]:
        if not path.exists():
            raise FileNotFoundError(f"Required input not found: {path}")

    news = pd.read_csv(news_path)
    links = pd.read_csv(links_path)
    returns = pd.read_csv(prices_path)
    config = load_ticker_config(config_path)

    news["published_date"] = pd.to_datetime(news["published_date"], errors="coerce")
    news["is_relevant"] = to_bool(news["is_relevant"])
    news["materiality"] = pd.to_numeric(news["materiality"], errors="coerce")
    news["confidence"] = pd.to_numeric(news["confidence"], errors="coerce")
    news = news.loc[news["classification_status"] == "success"].copy()

    ticker_to_group, group_to_tickers = build_ticker_maps(config)
    links["query_ticker"] = links["query_ticker"].astype(str).str.upper()
    links["published_date"] = pd.to_datetime(links["published_date"], errors="coerce")

    merged = news.merge(
        links[["article_id", "query_ticker"]].drop_duplicates(),
        on="article_id",
        how="left",
    )
    merged = merged.rename(columns={"query_ticker": "source_ticker"})
    merged["source_ticker"] = merged["source_ticker"].astype(str).str.upper()
    merged["source_group"] = merged["source_ticker"].map(ticker_to_group)

    merged = merged.loc[merged["is_relevant"] & merged["source_group"].notna()].copy()
    merged["sample_broad"] = merged["is_relevant"]
    merged["sample_strict"] = merged["sample_broad"] & (
        merged["relevance_type"] != "market_roundup_but_relevant"
    )
    merged["sample_very_strict"] = (
        merged["sample_strict"]
        & (merged["materiality"] >= 3)
        & (merged["confidence"] >= 4)
    )

    event_rows: list[dict[str, Any]] = []
    for row in merged.to_dict(orient="records"):
        source_ticker = row["source_ticker"]
        group_name = row["source_group"]
        competitors = [ticker for ticker in group_to_tickers.get(group_name, []) if ticker != source_ticker]
        for competitor_ticker in competitors:
            event_rows.append(
                {
                    **row,
                    "competitor_ticker": competitor_ticker,
                    "competitor_group": group_name,
                }
            )

    if not event_rows:
        raise ValueError("No relevant article/source_ticker/competitor_ticker rows were created.")

    panel = pd.DataFrame(event_rows)
    returns["date"] = pd.to_datetime(returns["date"], errors="coerce")
    returns["simple_return"] = pd.to_numeric(returns["simple_return"], errors="coerce")
    returns["abret_spy"] = pd.to_numeric(returns["abret_spy"], errors="coerce")

    trading_dates = sorted(
        returns.loc[returns["ticker"] == "SPY", "date"].dropna().drop_duplicates().tolist()
    )
    if not trading_dates:
        raise ValueError("No SPY trading dates found in daily_returns.csv.")

    event_trade_dates, event_trade_indices = map_to_trading_dates(panel["published_date"], trading_dates)
    panel["event_trade_date"] = event_trade_dates
    panel["event_trade_idx"] = event_trade_indices
    panel["published_date"] = panel["published_date"].dt.date
    panel["event_trade_date"] = pd.to_datetime(panel["event_trade_date"], errors="coerce")
    panel["event_trade_date"] = panel["event_trade_date"].dt.date
    panel["event_trade_day_offset"] = (
        pd.to_datetime(panel["event_trade_date"], errors="coerce")
        - pd.to_datetime(panel["published_date"], errors="coerce")
    ).dt.days

    simple_pivot = returns.pivot(index="date", columns="ticker", values="simple_return").sort_index()
    abret_spy_pivot = returns.pivot(index="date", columns="ticker", values="abret_spy").sort_index()

    t_dates: dict[int, list[pd.Timestamp | pd.NaT]] = {}
    for offset in range(4):
        offset_dates: list[pd.Timestamp | pd.NaT] = []
        for idx in event_trade_indices:
            if idx is None or idx + offset >= len(trading_dates):
                offset_dates.append(pd.NaT)
            else:
                offset_dates.append(trading_dates[idx + offset])
        t_dates[offset] = offset_dates
        panel[f"t{offset}_date"] = pd.to_datetime(offset_dates, errors="coerce").date

    competitor_return_columns: dict[str, list[float]] = {}
    source_return_columns: dict[str, list[float]] = {}
    for offset in range(4):
        competitor_return_columns[f"competitor_ret_t{offset}"] = []
        competitor_return_columns[f"competitor_abret_spy_t{offset}"] = []
        source_return_columns[f"source_ret_t{offset}"] = []
        source_return_columns[f"source_abret_spy_t{offset}"] = []

    for i, row in panel.iterrows():
        competitor_ticker = row["competitor_ticker"]
        source_ticker = row["source_ticker"]
        for offset in range(4):
            date_value = t_dates[offset][i]
            competitor_return_columns[f"competitor_ret_t{offset}"].append(
                get_value(simple_pivot, date_value, competitor_ticker)
            )
            competitor_return_columns[f"competitor_abret_spy_t{offset}"].append(
                get_value(abret_spy_pivot, date_value, competitor_ticker)
            )
            source_return_columns[f"source_ret_t{offset}"].append(
                get_value(simple_pivot, date_value, source_ticker)
            )
            source_return_columns[f"source_abret_spy_t{offset}"].append(
                get_value(abret_spy_pivot, date_value, source_ticker)
            )

    for column_name, values in {**competitor_return_columns, **source_return_columns}.items():
        panel[column_name] = values

    panel["competitor_car_0_1"] = panel.apply(
        lambda row: sum_or_nan([row["competitor_ret_t0"], row["competitor_ret_t1"]]), axis=1
    )
    panel["competitor_car_1_3"] = panel.apply(
        lambda row: sum_or_nan(
            [row["competitor_ret_t1"], row["competitor_ret_t2"], row["competitor_ret_t3"]]
        ),
        axis=1,
    )
    panel["competitor_car_abret_spy_0_1"] = panel.apply(
        lambda row: sum_or_nan([row["competitor_abret_spy_t0"], row["competitor_abret_spy_t1"]]),
        axis=1,
    )
    panel["competitor_car_abret_spy_1_3"] = panel.apply(
        lambda row: sum_or_nan(
            [
                row["competitor_abret_spy_t1"],
                row["competitor_abret_spy_t2"],
                row["competitor_abret_spy_t3"],
            ]
        ),
        axis=1,
    )
    panel["source_car_0_1"] = panel.apply(
        lambda row: sum_or_nan([row["source_ret_t0"], row["source_ret_t1"]]), axis=1
    )
    panel["source_car_abret_spy_0_1"] = panel.apply(
        lambda row: sum_or_nan([row["source_abret_spy_t0"], row["source_abret_spy_t1"]]), axis=1
    )

    output_columns = [
        "article_id",
        "source_ticker",
        "source_group",
        "competitor_ticker",
        "competitor_group",
        "published_date",
        "event_trade_date",
        "event_trade_day_offset",
        "t0_date",
        "t1_date",
        "t2_date",
        "t3_date",
        "title",
        "publisher",
        "linked_ticker_count",
        "linked_tickers",
        "stratum",
        "relevance_type",
        "primary_company",
        "primary_industry",
        "event_type",
        "target_company_sentiment",
        "news_scope",
        "expected_competitor_effect",
        "materiality",
        "confidence",
        "reasoning_short",
        "sample_broad",
        "sample_strict",
        "sample_very_strict",
        "competitor_ret_t0",
        "competitor_ret_t1",
        "competitor_ret_t2",
        "competitor_ret_t3",
        "competitor_car_0_1",
        "competitor_car_1_3",
        "competitor_abret_spy_t0",
        "competitor_abret_spy_t1",
        "competitor_abret_spy_t2",
        "competitor_abret_spy_t3",
        "competitor_car_abret_spy_0_1",
        "competitor_car_abret_spy_1_3",
        "source_ret_t0",
        "source_ret_t1",
        "source_car_0_1",
        "source_abret_spy_t0",
        "source_abret_spy_t1",
        "source_car_abret_spy_0_1",
    ]
    panel = panel[output_columns].sort_values(
        ["published_date", "article_id", "source_ticker", "competitor_ticker"]
    )

    ensure_dir(output_path.parent)
    panel.to_csv(output_path, index=False)

    print("Event panel build completed.")
    print(f"Output: {output_path}")
    print(f"Rows written: {len(panel):,}")
    print(f"Unique articles: {panel['article_id'].nunique():,}")
    print(f"Broad sample rows: {int(panel['sample_broad'].sum()):,}")
    print(f"Strict sample rows: {int(panel['sample_strict'].sum()):,}")
    print(f"Very strict sample rows: {int(panel['sample_very_strict'].sum()):,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
