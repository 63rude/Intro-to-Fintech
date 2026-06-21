"""Download raw corporate news for the Project 2 ticker universe.

This script supports:
- Finnhub company news
- Alpha Vantage News & Sentiment

It writes one JSONL file per source and date range under `data/raw/news/`.
Each row preserves the original API response item inside `raw_response_item`.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import requests

from utils import (
    PROJECT_ROOT,
    append_jsonl,
    ensure_dir,
    get_checkpoint_entries_for_run,
    get_date_chunks,
    get_unique_tickers,
    iso_utcnow,
    load_checkpoint,
    load_dotenv,
    load_ticker_config,
    parse_date,
    remove_checkpoint_entries_for_run,
    request_json,
    resolve_path,
    save_checkpoint,
    setup_logging,
)


FINNHUB_BASE_URL = "https://finnhub.io/api/v1/company-news"
ALPHAVANTAGE_BASE_URL = "https://www.alphavantage.co/query"
DEFAULT_CHUNK_DAYS = 31


class ApiResponseError(RuntimeError):
    """Raised when an API returns an application-level error."""


@dataclass
class SourceRunConfig:
    name: str
    output_path: Path
    checkpoint_path: Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch raw corporate news from Finnhub and Alpha Vantage."
    )
    parser.add_argument(
        "--source",
        required=True,
        choices=["finnhub", "alphavantage", "alpha_vantage", "all"],
        help="News source to query.",
    )
    parser.add_argument("--start", required=True, help="Start date in YYYY-MM-DD format.")
    parser.add_argument("--end", required=True, help="End date in YYYY-MM-DD format.")
    parser.add_argument(
        "--tickers",
        help="Optional comma-separated tickers. Defaults to config/competitor_groups.yaml.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=12.0,
        help="Seconds to sleep between API requests. Default: 12.",
    )
    parser.add_argument(
        "--limit-per-ticker",
        type=int,
        default=1000,
        help="Maximum raw items to collect per ticker per source. Default: 1000.",
    )
    parser.add_argument(
        "--chunk-days",
        type=int,
        default=DEFAULT_CHUNK_DAYS,
        help="Date-window chunk size used internally for resumable downloads.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild matching source/date-range outputs instead of resuming.",
    )
    return parser


def normalize_source_name(value: str) -> str:
    if value == "alpha_vantage":
        return "alphavantage"
    return value


def parse_tickers_arg(tickers_arg: str | None) -> list[str]:
    if not tickers_arg:
        return []
    tickers = [ticker.strip().upper() for ticker in tickers_arg.split(",")]
    return [ticker for ticker in tickers if ticker]


def get_sources(source_arg: str) -> list[str]:
    normalized = normalize_source_name(source_arg)
    if normalized == "all":
        return ["finnhub", "alphavantage"]
    return [normalized]


def get_api_key(source: str) -> str:
    if source == "finnhub":
        api_key = (
            os_environ("FINNHUB_API_KEY")
            or os_environ("FINNHUB_TOKEN")
        )
        if not api_key:
            raise SystemExit(
                "Missing Finnhub API key. Set FINNHUB_API_KEY in your shell or project .env file."
            )
        return api_key

    if source == "alphavantage":
        api_key = (
            os_environ("ALPHAVANTAGE_API_KEY")
            or os_environ("ALPHA_VANTAGE_API_KEY")
        )
        if not api_key:
            raise SystemExit(
                "Missing Alpha Vantage API key. Set ALPHAVANTAGE_API_KEY in your shell or project .env file."
            )
        return api_key

    raise SystemExit(f"Unsupported source: {source}")


def os_environ(key: str) -> str:
    import os

    return os.environ.get(key, "").strip()


def build_run_config(source: str, start_date: str, end_date: str) -> SourceRunConfig:
    output_dir = ensure_dir(PROJECT_ROOT / "data" / "raw" / "news")
    output_path = output_dir / f"{source}_news_{start_date}_{end_date}.jsonl"
    checkpoint_path = output_dir / "download_checkpoint.json"
    return SourceRunConfig(
        name=source,
        output_path=output_path,
        checkpoint_path=checkpoint_path,
    )


def build_chunk_key(
    source: str,
    overall_start: str,
    overall_end: str,
    ticker: str,
    chunk_start: str,
    chunk_end: str,
) -> str:
    return "|".join([source, overall_start, overall_end, ticker, chunk_start, chunk_end])


def collect_existing_chunk_keys(output_path: Path) -> set[str]:
    keys: set[str] = set()
    if not output_path.exists():
        return keys

    with output_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            source = str(record.get("source", "")).strip()
            overall_start = str(record.get("run_start_date", "")).strip()
            overall_end = str(record.get("run_end_date", "")).strip()
            ticker = str(record.get("query_ticker", "")).strip()
            chunk_start = str(record.get("start_date", "")).strip()
            chunk_end = str(record.get("end_date", "")).strip()
            if all([source, overall_start, overall_end, ticker, chunk_start, chunk_end]):
                keys.add(
                    build_chunk_key(
                        source=source,
                        overall_start=overall_start,
                        overall_end=overall_end,
                        ticker=ticker,
                        chunk_start=chunk_start,
                        chunk_end=chunk_end,
                    )
                )
    return keys


def is_rate_limit_message(message: str) -> bool:
    lowered = message.lower()
    return "rate limit" in lowered or "api call frequency" in lowered or "429" in lowered


def fetch_finnhub_news(
    session: requests.Session,
    ticker: str,
    chunk_start: date,
    chunk_end: date,
    api_key: str,
    logger: Any,
) -> list[dict[str, Any]]:
    payload = request_json(
        session=session,
        url=FINNHUB_BASE_URL,
        params={
            "symbol": ticker,
            "from": chunk_start.isoformat(),
            "to": chunk_end.isoformat(),
            "token": api_key,
        },
        logger=logger,
        service_name="Finnhub",
    )

    if isinstance(payload, dict) and payload.get("error"):
        raise ApiResponseError(str(payload["error"]))
    if not isinstance(payload, list):
        raise ApiResponseError(f"Unexpected Finnhub payload type: {type(payload).__name__}")
    return payload


def fetch_alphavantage_news(
    session: requests.Session,
    ticker: str,
    chunk_start: date,
    chunk_end: date,
    api_key: str,
    per_request_limit: int,
    logger: Any,
) -> list[dict[str, Any]]:
    payload = request_json(
        session=session,
        url=ALPHAVANTAGE_BASE_URL,
        params={
            "function": "NEWS_SENTIMENT",
            "tickers": ticker,
            "time_from": f"{chunk_start.strftime('%Y%m%d')}T0000",
            "time_to": f"{chunk_end.strftime('%Y%m%d')}T2359",
            "sort": "EARLIEST",
            "limit": per_request_limit,
            "apikey": api_key,
        },
        logger=logger,
        service_name="Alpha Vantage",
    )

    if isinstance(payload, dict):
        for key in ("Note", "Information", "Error Message"):
            if payload.get(key):
                raise ApiResponseError(str(payload[key]))
        feed = payload.get("feed", [])
        if not isinstance(feed, list):
            raise ApiResponseError("Alpha Vantage response contained a non-list feed field.")
        return feed

    raise ApiResponseError(
        f"Unexpected Alpha Vantage payload type: {type(payload).__name__}"
    )


def fetch_source_chunk(
    source: str,
    session: requests.Session,
    ticker: str,
    chunk_start: date,
    chunk_end: date,
    api_key: str,
    remaining_limit: int,
    logger: Any,
) -> list[dict[str, Any]]:
    if source == "finnhub":
        return fetch_finnhub_news(
            session=session,
            ticker=ticker,
            chunk_start=chunk_start,
            chunk_end=chunk_end,
            api_key=api_key,
            logger=logger,
        )

    if source == "alphavantage":
        per_request_limit = min(1000, max(1, remaining_limit))
        return fetch_alphavantage_news(
            session=session,
            ticker=ticker,
            chunk_start=chunk_start,
            chunk_end=chunk_end,
            api_key=api_key,
            per_request_limit=per_request_limit,
            logger=logger,
        )

    raise SystemExit(f"Unsupported source: {source}")


def build_raw_rows(
    source: str,
    ticker: str,
    run_start: str,
    run_end: str,
    chunk_start: str,
    chunk_end: str,
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    downloaded_at = iso_utcnow()
    rows: list[dict[str, Any]] = []
    for item in items:
        rows.append(
            {
                "source": source,
                "query_ticker": ticker,
                "downloaded_at": downloaded_at,
                "run_start_date": run_start,
                "run_end_date": run_end,
                "start_date": chunk_start,
                "end_date": chunk_end,
                "raw_response_item": item,
            }
        )
    return rows


def reset_run_outputs(
    source: str,
    config: SourceRunConfig,
    overall_start: str,
    overall_end: str,
    logger: Any,
) -> None:
    if config.output_path.exists():
        config.output_path.unlink()
        logger.info("Removed existing output file for forced rerun: %s", config.output_path)

    checkpoint = load_checkpoint(config.checkpoint_path)
    changed = remove_checkpoint_entries_for_run(
        checkpoint=checkpoint,
        source=source,
        overall_start=overall_start,
        overall_end=overall_end,
    )
    if changed:
        save_checkpoint(config.checkpoint_path, checkpoint)
        logger.info(
            "Removed %s checkpoint entries for forced rerun of %s %s to %s.",
            changed,
            source,
            overall_start,
            overall_end,
        )


def run_source(
    source: str,
    tickers: list[str],
    overall_start: date,
    overall_end: date,
    sleep_seconds: float,
    limit_per_ticker: int,
    chunk_days: int,
    force: bool,
    logger: Any,
) -> None:
    api_key = get_api_key(source)
    run_config = build_run_config(source, overall_start.isoformat(), overall_end.isoformat())
    ensure_dir(run_config.output_path.parent)

    if force:
        reset_run_outputs(
            source=source,
            config=run_config,
            overall_start=overall_start.isoformat(),
            overall_end=overall_end.isoformat(),
            logger=logger,
        )

    checkpoint = load_checkpoint(run_config.checkpoint_path)
    completed_entries = get_checkpoint_entries_for_run(
        checkpoint=checkpoint,
        source=source,
        overall_start=overall_start.isoformat(),
        overall_end=overall_end.isoformat(),
        allowed_statuses={"success", "empty"},
    )
    completed_keys = set(completed_entries.keys())
    completed_keys.update(collect_existing_chunk_keys(run_config.output_path))

    chunks = list(get_date_chunks(overall_start, overall_end, chunk_days=chunk_days))
    logger.info(
        "Starting source=%s tickers=%s chunks_per_ticker=%s output=%s",
        source,
        len(tickers),
        len(chunks),
        run_config.output_path,
    )

    session = requests.Session()
    total_requests = 0

    for ticker_index, ticker in enumerate(tickers, start=1):
        items_for_ticker = 0
        logger.info("[%s/%s] %s: starting", ticker_index, len(tickers), ticker)

        for chunk_index, (chunk_start, chunk_end) in enumerate(chunks, start=1):
            remaining_limit = limit_per_ticker - items_for_ticker
            if remaining_limit <= 0:
                logger.info(
                    "%s: reached limit-per-ticker=%s for source=%s",
                    ticker,
                    limit_per_ticker,
                    source,
                )
                break

            key = build_chunk_key(
                source=source,
                overall_start=overall_start.isoformat(),
                overall_end=overall_end.isoformat(),
                ticker=ticker,
                chunk_start=chunk_start.isoformat(),
                chunk_end=chunk_end.isoformat(),
            )
            if key in completed_keys:
                logger.info(
                    "[%s/%s][chunk %s/%s] %s %s to %s already completed, skipping",
                    ticker_index,
                    len(tickers),
                    chunk_index,
                    len(chunks),
                    ticker,
                    chunk_start.isoformat(),
                    chunk_end.isoformat(),
                )
                continue

            logger.info(
                "[%s/%s][chunk %s/%s] Fetching %s %s news from %s to %s",
                ticker_index,
                len(tickers),
                chunk_index,
                len(chunks),
                source,
                ticker,
                chunk_start.isoformat(),
                chunk_end.isoformat(),
            )

            try:
                items = fetch_source_chunk(
                    source=source,
                    session=session,
                    ticker=ticker,
                    chunk_start=chunk_start,
                    chunk_end=chunk_end,
                    api_key=api_key,
                    remaining_limit=remaining_limit,
                    logger=logger,
                )
            except ApiResponseError as exc:
                logger.error(
                    "%s %s %s to %s: API error: %s",
                    source,
                    ticker,
                    chunk_start.isoformat(),
                    chunk_end.isoformat(),
                    exc,
                )
                if is_rate_limit_message(str(exc)):
                    logger.info("Sleeping %.1f seconds after rate-limit style message.", sleep_seconds)
                    time.sleep(sleep_seconds)
                continue
            except requests.RequestException as exc:
                logger.error(
                    "%s %s %s to %s: request failed after retries: %s",
                    source,
                    ticker,
                    chunk_start.isoformat(),
                    chunk_end.isoformat(),
                    exc,
                )
                continue

            total_requests += 1
            if items:
                rows = build_raw_rows(
                    source=source,
                    ticker=ticker,
                    run_start=overall_start.isoformat(),
                    run_end=overall_end.isoformat(),
                    chunk_start=chunk_start.isoformat(),
                    chunk_end=chunk_end.isoformat(),
                    items=items,
                )
                append_jsonl(run_config.output_path, rows)
                items_for_ticker += len(items)
                logger.info(
                    "%s %s %s to %s: wrote %s rows (ticker total=%s)",
                    source,
                    ticker,
                    chunk_start.isoformat(),
                    chunk_end.isoformat(),
                    len(rows),
                    items_for_ticker,
                )
            else:
                logger.warning(
                    "%s %s %s to %s: empty response",
                    source,
                    ticker,
                    chunk_start.isoformat(),
                    chunk_end.isoformat(),
                )

            checkpoint.setdefault("downloads", {})[key] = {
                "source": source,
                "query_ticker": ticker,
                "run_start_date": overall_start.isoformat(),
                "run_end_date": overall_end.isoformat(),
                "start_date": chunk_start.isoformat(),
                "end_date": chunk_end.isoformat(),
                "status": "success" if items else "empty",
                "item_count": len(items),
                "updated_at": iso_utcnow(),
                "output_file": str(run_config.output_path),
            }
            save_checkpoint(run_config.checkpoint_path, checkpoint)
            completed_keys.add(key)

            logger.info("Sleeping %.1f seconds before the next request.", sleep_seconds)
            time.sleep(sleep_seconds)

    logger.info(
        "Finished source=%s output=%s total_requests=%s",
        source,
        run_config.output_path,
        total_requests,
    )


def main() -> int:
    load_dotenv()
    args = build_parser().parse_args()

    start_date = parse_date(args.start)
    end_date = parse_date(args.end)
    if end_date < start_date:
        raise SystemExit("--end must be on or after --start.")
    if args.chunk_days <= 0:
        raise SystemExit("--chunk-days must be a positive integer.")
    if args.limit_per_ticker <= 0:
        raise SystemExit("--limit-per-ticker must be a positive integer.")

    requested_tickers = parse_tickers_arg(args.tickers)
    if requested_tickers:
        tickers = requested_tickers
    else:
        config = load_ticker_config(resolve_path("config/competitor_groups.yaml"))
        tickers = get_unique_tickers(config)
    if not tickers:
        raise SystemExit("No tickers found. Check config/competitor_groups.yaml or --tickers.")

    log_dir = ensure_dir(PROJECT_ROOT / "outputs" / "logs")
    logger = setup_logging("fetch_news", log_dir)

    logger.info(
        "Project root=%s sources=%s start=%s end=%s tickers=%s limit_per_ticker=%s chunk_days=%s force=%s",
        PROJECT_ROOT,
        get_sources(args.source),
        start_date.isoformat(),
        end_date.isoformat(),
        len(tickers),
        args.limit_per_ticker,
        args.chunk_days,
        args.force,
    )

    try:
        for source in get_sources(args.source):
            run_source(
                source=source,
                tickers=tickers,
                overall_start=start_date,
                overall_end=end_date,
                sleep_seconds=args.sleep,
                limit_per_ticker=args.limit_per_ticker,
                chunk_days=args.chunk_days,
                force=args.force,
                logger=logger,
            )
    except KeyboardInterrupt:
        logger.warning("Interrupted by user.")
        return 130
    except SystemExit:
        raise
    except Exception:
        logger.exception("Unhandled error during news download.")
        return 1

    logger.info("News download run completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
