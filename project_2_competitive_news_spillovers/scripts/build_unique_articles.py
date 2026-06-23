"""
Build unique article dataset for LLM classification.

Input:
    data/interim/news_basic_clean.csv

Outputs:
    data/interim/news_unique_articles.csv
    data/interim/news_article_ticker_links.csv

Why:
    The same article may appear under multiple tickers.
    We do not want to pay the LLM to classify the same article many times.
    So we classify unique articles once, then map classifications back to ticker-level rows.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import pandas as pd


def clean_text(x) -> str:
    if pd.isna(x):
        return ""
    return str(x).strip()


def norm_key(x) -> str:
    return clean_text(x).lower().replace("\n", " ").replace("\r", " ").strip()


def make_article_key(row: pd.Series) -> str:
    """
    Prefer URL as unique identifier.
    Fall back to title + published_date + publisher.
    """
    url = norm_key(row.get("url", ""))
    title = norm_key(row.get("title", ""))
    date = norm_key(row.get("published_date", ""))
    publisher = norm_key(row.get("publisher", ""))

    if url:
        raw = f"url::{url}"
    else:
        raw = f"title_date_publisher::{title}::{date}::{publisher}"

    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create unique article dataset for LLM classification.")
    parser.add_argument(
        "--input",
        default="data/interim/news_basic_clean.csv",
        help="Input cleaned ticker-level news CSV.",
    )
    parser.add_argument(
        "--articles-output",
        default="data/interim/news_unique_articles.csv",
        help="Output unique article CSV.",
    )
    parser.add_argument(
        "--links-output",
        default="data/interim/news_article_ticker_links.csv",
        help="Output article-to-ticker link CSV.",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    articles_output = Path(args.articles_output)
    links_output = Path(args.links_output)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    df = pd.read_csv(input_path)

    required_cols = [
        "news_id",
        "query_ticker",
        "published_at",
        "published_date",
        "title",
        "summary",
        "url",
        "publisher",
    ]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df["article_id"] = df.apply(make_article_key, axis=1)

    # One row per unique article.
    # Keep the first occurrence as representative article text.
    article_cols = [
        "article_id",
        "source",
        "published_at",
        "published_date",
        "title",
        "summary",
        "url",
        "publisher",
        "image_url",
        "category",
    ]
    article_cols = [c for c in article_cols if c in df.columns]

    articles = (
        df.sort_values(["published_at", "query_ticker"])
        .drop_duplicates(subset=["article_id"], keep="first")[article_cols]
        .copy()
    )

    # Add metadata useful for inspection.
    article_stats = (
        df.groupby("article_id")
        .agg(
            linked_ticker_count=("query_ticker", "nunique"),
            linked_tickers=("query_ticker", lambda x: ";".join(sorted(set(map(str, x))))),
            duplicate_row_count=("news_id", "count"),
        )
        .reset_index()
    )

    articles = articles.merge(article_stats, on="article_id", how="left")

    # Ticker-level link table.
    link_cols = [
        "article_id",
        "news_id",
        "query_ticker",
        "related_tickers",
        "published_at",
        "published_date",
        "title",
        "url",
        "publisher",
    ]
    link_cols = [c for c in link_cols if c in df.columns]

    links = (
        df[link_cols]
        .drop_duplicates(subset=["article_id", "query_ticker"], keep="first")
        .copy()
    )

    articles_output.parent.mkdir(parents=True, exist_ok=True)
    links_output.parent.mkdir(parents=True, exist_ok=True)

    articles.to_csv(articles_output, index=False)
    links.to_csv(links_output, index=False)

    print("\nUnique article build completed.")
    print(f"Ticker-level input rows:     {len(df):,}")
    print(f"Unique articles:             {len(articles):,}")
    print(f"Article-ticker links:        {len(links):,}")
    print(f"Repeated article rows saved: {len(df) - len(articles):,}")
    print(f"Articles output:             {articles_output}")
    print(f"Links output:                {links_output}")

    print("\nTop linked ticker counts:")
    print(articles["linked_ticker_count"].value_counts().sort_index().to_string())

    print("\nArticles with most linked tickers:")
    preview_cols = ["linked_ticker_count", "linked_tickers", "published_date", "title", "publisher"]
    print(
        articles.sort_values("linked_ticker_count", ascending=False)[preview_cols]
        .head(20)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()