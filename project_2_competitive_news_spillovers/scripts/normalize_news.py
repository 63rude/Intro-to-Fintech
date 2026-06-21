"""Normalize raw Finnhub and Alpha Vantage news into a unified CSV dataset."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

from utils import (
    PROJECT_ROOT,
    ensure_dir,
    iter_jsonl,
    load_dotenv,
    normalize_iso_datetime,
    resolve_path,
    setup_logging,
    stable_hash,
)


OUTPUT_COLUMNS = [
    "news_id",
    "source",
    "query_ticker",
    "related_tickers",
    "published_at",
    "published_date",
    "title",
    "summary",
    "url",
    "publisher",
    "image_url",
    "category",
    "source_sentiment_score",
    "source_sentiment_label",
    "source_relevance_score",
    "raw_event_id",
    "downloaded_at",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Normalize raw news JSONL files into one CSV.")
    parser.add_argument(
        "--input",
        required=True,
        help="Input raw news JSONL file or directory.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output CSV path for the normalized dataset.",
    )
    return parser


def discover_input_files(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    if input_path.is_dir():
        return sorted(path for path in input_path.rglob("*.jsonl") if path.is_file())
    raise FileNotFoundError(f"Input path not found: {input_path}")


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def stringify_related_tickers(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        raw_parts = value.replace(",", ";").split(";")
        tickers = [part.strip().upper() for part in raw_parts if part.strip()]
        return ";".join(dict.fromkeys(tickers))
    if isinstance(value, list):
        tickers = [str(part).strip().upper() for part in value if str(part).strip()]
        return ";".join(dict.fromkeys(tickers))
    return clean_text(value)


def find_query_ticker_relevance(ticker_sentiment: Any, query_ticker: str) -> str:
    if not isinstance(ticker_sentiment, list):
        return ""
    query_upper = query_ticker.upper()
    for item in ticker_sentiment:
        if not isinstance(item, dict):
            continue
        if str(item.get("ticker", "")).upper() == query_upper:
            return clean_text(item.get("relevance_score"))
    return ""


def extract_related_tickers_from_alpha(item: dict[str, Any]) -> str:
    ticker_sentiment = item.get("ticker_sentiment")
    if not isinstance(ticker_sentiment, list):
        return ""
    tickers = []
    for entry in ticker_sentiment:
        if isinstance(entry, dict) and entry.get("ticker"):
            tickers.append(str(entry["ticker"]).strip().upper())
    return ";".join(dict.fromkeys(tickers))


def normalize_raw_record(record: dict[str, Any]) -> dict[str, str]:
    source = clean_text(record.get("source")).lower()
    query_ticker = clean_text(record.get("query_ticker")).upper()
    item = record.get("raw_response_item") or {}
    if not isinstance(item, dict):
        item = {}

    published_at = ""
    related_tickers = ""
    publisher = ""
    image_url = ""
    category = ""
    source_sentiment_score = ""
    source_sentiment_label = ""
    source_relevance_score = ""
    raw_event_id = ""

    if source == "finnhub":
        published_at = normalize_iso_datetime(item.get("datetime"))
        related_tickers = stringify_related_tickers(item.get("related"))
        publisher = clean_text(item.get("source"))
        image_url = clean_text(item.get("image"))
        category = clean_text(item.get("category"))
        raw_event_id = clean_text(item.get("id"))
        title = clean_text(item.get("headline"))
        summary = clean_text(item.get("summary"))
        url = clean_text(item.get("url"))
    elif source == "alphavantage":
        published_at = normalize_iso_datetime(item.get("time_published"))
        related_tickers = extract_related_tickers_from_alpha(item)
        publisher = clean_text(item.get("source"))
        image_url = clean_text(item.get("banner_image"))
        category = clean_text(item.get("category_within_source"))
        source_sentiment_score = clean_text(item.get("overall_sentiment_score"))
        source_sentiment_label = clean_text(item.get("overall_sentiment_label"))
        source_relevance_score = find_query_ticker_relevance(
            item.get("ticker_sentiment"),
            query_ticker,
        )
        raw_event_id = clean_text(item.get("id")) or clean_text(item.get("article_id"))
        title = clean_text(item.get("title"))
        summary = clean_text(item.get("summary"))
        url = clean_text(item.get("url"))
    else:
        published_at = normalize_iso_datetime(item.get("published_at") or item.get("datetime"))
        related_tickers = stringify_related_tickers(item.get("related_tickers"))
        publisher = clean_text(item.get("publisher"))
        image_url = clean_text(item.get("image_url"))
        category = clean_text(item.get("category"))
        source_sentiment_score = clean_text(item.get("source_sentiment_score"))
        source_sentiment_label = clean_text(item.get("source_sentiment_label"))
        source_relevance_score = clean_text(item.get("source_relevance_score"))
        raw_event_id = clean_text(item.get("raw_event_id"))
        title = clean_text(item.get("title") or item.get("headline"))
        summary = clean_text(item.get("summary"))
        url = clean_text(item.get("url"))

    published_date = published_at[:10] if published_at else ""
    news_id = stable_hash(source, title, url, published_at, query_ticker)

    return {
        "news_id": news_id,
        "source": source,
        "query_ticker": query_ticker,
        "related_tickers": related_tickers,
        "published_at": published_at,
        "published_date": published_date,
        "title": title,
        "summary": summary,
        "url": url,
        "publisher": publisher,
        "image_url": image_url,
        "category": category,
        "source_sentiment_score": source_sentiment_score,
        "source_sentiment_label": source_sentiment_label,
        "source_relevance_score": source_relevance_score,
        "raw_event_id": raw_event_id,
        "downloaded_at": clean_text(record.get("downloaded_at")),
    }


def write_csv(output_path: Path, rows: list[dict[str, str]]) -> None:
    ensure_dir(output_path.parent)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    load_dotenv()
    args = build_parser().parse_args()

    input_path = resolve_path(args.input)
    output_path = resolve_path(args.output)

    log_dir = ensure_dir(PROJECT_ROOT / "outputs" / "logs")
    logger = setup_logging("normalize_news", log_dir)
    logger.info("Normalizing raw news from %s into %s", input_path, output_path)

    files = discover_input_files(input_path)
    if not files:
        raise SystemExit(f"No JSONL files found under {input_path}")

    normalized_rows: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    skipped_duplicates = 0

    for file_path in files:
        logger.info("Reading raw file: %s", file_path)
        for raw_record in iter_jsonl(file_path):
            normalized = normalize_raw_record(raw_record)
            news_id = normalized["news_id"]
            if news_id in seen_ids:
                skipped_duplicates += 1
                continue
            seen_ids.add(news_id)
            normalized_rows.append(normalized)

    normalized_rows.sort(
        key=lambda row: (
            row["published_at"],
            row["source"],
            row["query_ticker"],
            row["title"],
        )
    )
    write_csv(output_path, normalized_rows)
    logger.info(
        "Wrote %s normalized rows to %s (skipped %s exact duplicates)",
        len(normalized_rows),
        output_path,
        skipped_duplicates,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
