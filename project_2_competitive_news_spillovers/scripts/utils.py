"""Shared utilities for the Project 2 news data pipeline."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

import requests
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    if path.exists():
        return path.resolve()
    if path.parts and path.parts[0] == PROJECT_ROOT.name:
        return path.resolve()
    return PROJECT_ROOT / path


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_dotenv(dotenv_path: Path | None = None, override: bool = False) -> None:
    candidate = dotenv_path or PROJECT_ROOT / ".env"
    if not candidate.exists():
        return

    with candidate.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()

            if value and len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
                value = value[1:-1]

            if override or key not in os.environ:
                os.environ[key] = value


def load_ticker_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    if not isinstance(config, dict):
        raise ValueError(f"Ticker config must be a mapping: {path}")
    return config


def get_unique_tickers(config: dict[str, Any]) -> list[str]:
    industries = config.get("industries", {})
    seen: set[str] = set()
    tickers: list[str] = []
    if not isinstance(industries, dict):
        return tickers

    for group_data in industries.values():
        if not isinstance(group_data, dict):
            continue
        for ticker in group_data.get("tickers", []):
            ticker_text = str(ticker).strip().upper()
            if ticker_text and ticker_text not in seen:
                seen.add(ticker_text)
                tickers.append(ticker_text)
    return tickers


def append_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    ensure_dir(path.parent)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"Invalid date '{value}'. Expected YYYY-MM-DD.") from exc


def get_date_chunks(start_date: date, end_date: date, chunk_days: int) -> Iterator[tuple[date, date]]:
    current = start_date
    while current <= end_date:
        chunk_end = min(current + timedelta(days=chunk_days - 1), end_date)
        yield current, chunk_end
        current = chunk_end + timedelta(days=1)


def iso_utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_iso_datetime(value: Any) -> str:
    if value is None or value == "":
        return ""

    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc).replace(
            microsecond=0
        ).isoformat()

    text = str(value).strip()
    if not text:
        return ""

    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    for fmt in ("%Y%m%dT%H%M", "%Y%m%dT%H%M%S"):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            pass

    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return ""

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.replace(microsecond=0).isoformat()


def stable_hash(*parts: Any) -> str:
    normalized = "||".join("" if part is None else str(part) for part in parts)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def sanitize_params(params: dict[str, Any]) -> dict[str, Any]:
    sanitized = dict(params)
    for secret_key in ("apikey", "token", "api_key"):
        if secret_key in sanitized:
            sanitized[secret_key] = "***"
    return sanitized


def request_json(
    session: requests.Session,
    url: str,
    params: dict[str, Any],
    logger: Any,
    service_name: str,
    timeout: int = 60,
    max_retries: int = 5,
    initial_backoff: float = 2.0,
) -> Any:
    backoff = initial_backoff
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            response = session.get(url, params=params, timeout=timeout)
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                sleep_seconds = float(retry_after) if retry_after else backoff
                logger.warning(
                    "%s rate limited on attempt %s/%s. Sleeping %.1f seconds.",
                    service_name,
                    attempt,
                    max_retries,
                    sleep_seconds,
                )
                time.sleep(sleep_seconds)
                backoff *= 2
                continue

            if 500 <= response.status_code < 600:
                logger.warning(
                    "%s server error %s on attempt %s/%s for params=%s",
                    service_name,
                    response.status_code,
                    attempt,
                    max_retries,
                    sanitize_params(params),
                )
                response.raise_for_status()

            response.raise_for_status()
            try:
                return response.json()
            except ValueError as exc:
                excerpt = response.text[:200].replace("\n", " ")
                raise requests.RequestException(
                    f"{service_name} returned non-JSON content: {excerpt}"
                ) from exc
        except requests.RequestException as exc:
            last_error = exc
            if attempt >= max_retries:
                break
            logger.warning(
                "%s request failed on attempt %s/%s for params=%s: %s",
                service_name,
                attempt,
                max_retries,
                sanitize_params(params),
                exc,
            )
            logger.info("Sleeping %.1f seconds before retry.", backoff)
            time.sleep(backoff)
            backoff *= 2

    if last_error is None:
        last_error = requests.RequestException(f"{service_name} request failed.")
    raise last_error


def setup_logging(name: str, log_dir: Path) -> logging.Logger:
    ensure_dir(log_dir)
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"{name}_{timestamp}.log"
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    logger.info("Logging to %s", log_path)
    return logger


def load_checkpoint(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"downloads": {}}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        return {"downloads": {}}
    data.setdefault("downloads", {})
    return data


def save_checkpoint(path: Path, checkpoint: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(checkpoint, handle, indent=2, ensure_ascii=False)


def get_checkpoint_entries_for_run(
    checkpoint: dict[str, Any],
    source: str,
    overall_start: str,
    overall_end: str,
    allowed_statuses: set[str],
) -> dict[str, dict[str, Any]]:
    entries = checkpoint.get("downloads", {})
    if not isinstance(entries, dict):
        return {}

    matched: dict[str, dict[str, Any]] = {}
    for key, value in entries.items():
        if not isinstance(value, dict):
            continue
        if value.get("source") != source:
            continue
        if value.get("run_start_date") != overall_start:
            continue
        if value.get("run_end_date") != overall_end:
            continue
        if value.get("status") not in allowed_statuses:
            continue
        matched[key] = value
    return matched


def remove_checkpoint_entries_for_run(
    checkpoint: dict[str, Any],
    source: str,
    overall_start: str,
    overall_end: str,
) -> int:
    entries = checkpoint.get("downloads", {})
    if not isinstance(entries, dict):
        checkpoint["downloads"] = {}
        return 0

    keys_to_delete = [
        key
        for key, value in entries.items()
        if isinstance(value, dict)
        and value.get("source") == source
        and value.get("run_start_date") == overall_start
        and value.get("run_end_date") == overall_end
    ]

    for key in keys_to_delete:
        del entries[key]
    return len(keys_to_delete)
