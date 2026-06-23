"""Classify news articles with the OpenAI API using concurrent, resumable outputs."""

from __future__ import annotations

import argparse
import csv
import json
import os
import threading
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from typing import Any

import pandas as pd
import requests
from requests.adapters import HTTPAdapter

from utils import ensure_dir, iso_utcnow, load_dotenv, resolve_path


INPUT_COLUMNS = [
    "article_id",
    "published_date",
    "title",
    "summary",
    "publisher",
    "linked_ticker_count",
    "linked_tickers",
    "stratum",
]

CLASSIFICATION_COLUMNS = [
    "classification_status",
    "is_relevant",
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
    "model",
    "input_tokens",
    "output_tokens",
    "estimated_cost_usd",
    "classified_at",
]

OUTPUT_COLUMNS = INPUT_COLUMNS + CLASSIFICATION_COLUMNS

ALLOWED_VALUES = {
    "relevance_type": {
        "target_company_news",
        "competitor_company_news",
        "industry_news",
        "macro_policy_news",
        "market_roundup_but_relevant",
        "not_relevant",
    },
    "primary_industry": {
        "autos_ev",
        "semiconductors_ai",
        "big_tech_cloud",
        "airlines_travel",
        "banks_finance",
        "macro_market",
        "other",
        "unclear",
        "not_applicable",
    },
    "event_type": {
        "earnings_or_guidance",
        "analyst_rating_or_price_target",
        "product_or_technology",
        "partnership_or_contract",
        "merger_acquisition_investment",
        "legal_regulatory_policy",
        "supply_chain_or_production",
        "demand_sales_or_deliveries",
        "management_or_governance",
        "financing_capital_return",
        "macro_rates_tariffs_oil_geopolitics",
        "market_roundup",
        "investment_advice_or_etf",
        "other",
        "not_applicable",
    },
    "target_company_sentiment": {
        "positive",
        "negative",
        "mixed",
        "neutral",
        "unclear",
        "not_applicable",
    },
    "news_scope": {
        "firm_specific",
        "industry_wide",
        "macro_wide",
        "mixed",
        "unclear",
        "not_applicable",
    },
    "expected_competitor_effect": {
        "positive_for_competitors",
        "negative_for_competitors",
        "same_direction_contagion",
        "opposite_direction_competition",
        "neutral_or_no_clear_effect",
        "unclear",
        "not_applicable",
    },
}

CLASSIFICATION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "is_relevant",
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
    ],
    "properties": {
        "is_relevant": {"type": "boolean"},
        "relevance_type": {"type": "string", "enum": sorted(ALLOWED_VALUES["relevance_type"])},
        "primary_company": {"type": "string"},
        "primary_industry": {"type": "string", "enum": sorted(ALLOWED_VALUES["primary_industry"])},
        "event_type": {"type": "string", "enum": sorted(ALLOWED_VALUES["event_type"])},
        "target_company_sentiment": {
            "type": "string",
            "enum": sorted(ALLOWED_VALUES["target_company_sentiment"]),
        },
        "news_scope": {"type": "string", "enum": sorted(ALLOWED_VALUES["news_scope"])},
        "expected_competitor_effect": {
            "type": "string",
            "enum": sorted(ALLOWED_VALUES["expected_competitor_effect"]),
        },
        "materiality": {"type": "integer", "minimum": 0, "maximum": 5},
        "confidence": {"type": "integer", "minimum": 1, "maximum": 5},
        "reasoning_short": {"type": "string"},
    },
}


class OpenAIAPIError(RuntimeError):
    """Raised for non-transient OpenAI API errors."""


class StructuredOutputUnsupported(RuntimeError):
    """Raised when the API/model rejects structured output parameters."""


@dataclass
class ClassificationResult:
    payload: dict[str, Any]
    raw_response: dict[str, Any]
    input_tokens: int
    output_tokens: int


@dataclass
class WorkResult:
    article_id: str
    output_row: dict[str, Any]
    raw_row: dict[str, Any]
    success: bool
    input_tokens: int
    output_tokens: int
    estimated_cost: float | str


_THREAD_LOCAL = threading.local()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Classify sampled news articles with OpenAI.")
    parser.add_argument(
        "--input",
        default="data/processed/llm_input/llm_input_sample_n20_per_stratum.csv",
        help="Input sampled article CSV.",
    )
    parser.add_argument(
        "--prompt-file",
        default="prompts/news_spillover_classification_prompt.md",
        help="Prompt template path.",
    )
    parser.add_argument(
        "--output",
        default="data/processed/llm_output/llm_classifications_sample_n20_per_stratum.csv",
        help="CSV output path for classifications.",
    )
    parser.add_argument(
        "--raw-output",
        default="",
        help="Optional raw JSONL output path. Defaults next to the CSV output.",
    )
    parser.add_argument(
        "--model",
        default="",
        help="Optional model override. Defaults to OPENAI_MODEL from .env/environment.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional max number of new articles to process in this run.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=12,
        help="Number of concurrent OpenAI requests to run. Increase until you approach rate limits.",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.0,
        help="Optional pause after each completed request. Default is 0 for maximum throughput.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=5,
        help="Maximum retries for transient API errors.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=120,
        help="Request timeout in seconds.",
    )
    parser.add_argument(
        "--structured-output",
        choices=["auto", "on", "off"],
        default="auto",
        help="Attempt JSON schema output when supported.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="Sampling temperature for the API call.",
    )
    parser.add_argument(
        "--input-cost-per-1m",
        type=float,
        default=None,
        help="Optional input token price in USD per 1M tokens for estimated cost.",
    )
    parser.add_argument(
        "--output-cost-per-1m",
        type=float,
        default=None,
        help="Optional output token price in USD per 1M tokens for estimated cost.",
    )
    return parser


def infer_raw_output_path(output_path):
    suffix = output_path.stem.replace("llm_classifications", "raw_responses")
    return output_path.with_name(f"{suffix}.jsonl")


def load_existing_ids(output_path) -> set[str]:
    if not output_path.exists():
        return set()
    try:
        existing = pd.read_csv(output_path, usecols=["article_id"])
    except ValueError:
        existing = pd.read_csv(output_path)
    return {str(value) for value in existing["article_id"].dropna().astype(str)}


def ensure_csv_header(path) -> None:
    ensure_dir(path.parent)
    if path.exists():
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()


def append_csv_row(path, row: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writerow({column: row.get(column, "") for column in OUTPUT_COLUMNS})


def append_jsonl_row(path, row: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False))
        handle.write("\n")


def read_text(path) -> str:
    with path.open("r", encoding="utf-8") as handle:
        return handle.read().strip()


def parse_response_text(raw_response: dict[str, Any]) -> str:
    if isinstance(raw_response.get("output_text"), str) and raw_response["output_text"].strip():
        return raw_response["output_text"].strip()

    output = raw_response.get("output")
    if isinstance(output, list):
        parts: list[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            for content in item.get("content", []):
                if not isinstance(content, dict):
                    continue
                text_value = content.get("text")
                if isinstance(text_value, str) and text_value.strip():
                    parts.append(text_value.strip())
        if parts:
            return "\n".join(parts).strip()
    return ""


def parse_usage(raw_response: dict[str, Any]) -> tuple[int, int]:
    usage = raw_response.get("usage")
    if not isinstance(usage, dict):
        return 0, 0

    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    if not output_tokens and isinstance(usage.get("output_tokens_details"), dict):
        output_tokens = usage.get("output_tokens_details", {}).get("text_tokens", 0)
    return int(input_tokens or 0), int(output_tokens or 0)


def safe_json_loads(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped:
        raise ValueError("Model returned empty text.")

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        parsed = json.loads(stripped[start : end + 1])

    if not isinstance(parsed, dict):
        raise ValueError("Model output is not a JSON object.")
    return parsed


def normalize_boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    raise ValueError(f"Invalid boolean value: {value!r}")


def normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    normalized["is_relevant"] = normalize_boolean(payload.get("is_relevant"))
    normalized["relevance_type"] = str(payload.get("relevance_type", "")).strip()
    normalized["primary_company"] = str(payload.get("primary_company", "")).strip() or "unclear"
    normalized["primary_industry"] = str(payload.get("primary_industry", "")).strip()
    normalized["event_type"] = str(payload.get("event_type", "")).strip()
    normalized["target_company_sentiment"] = str(payload.get("target_company_sentiment", "")).strip()
    normalized["news_scope"] = str(payload.get("news_scope", "")).strip()
    normalized["expected_competitor_effect"] = str(payload.get("expected_competitor_effect", "")).strip()
    normalized["materiality"] = int(payload.get("materiality"))
    normalized["confidence"] = int(payload.get("confidence"))
    normalized["reasoning_short"] = str(payload.get("reasoning_short", "")).strip()

    if not normalized["is_relevant"]:
        normalized["relevance_type"] = "not_relevant"
        normalized["primary_industry"] = "not_applicable"
        normalized["event_type"] = "not_applicable"
        normalized["target_company_sentiment"] = "not_applicable"
        normalized["news_scope"] = "not_applicable"
        normalized["expected_competitor_effect"] = "not_applicable"
        normalized["materiality"] = 0

    for field_name, allowed in ALLOWED_VALUES.items():
        if normalized[field_name] not in allowed:
            raise ValueError(f"Invalid value for {field_name}: {normalized[field_name]!r}")

    if normalized["materiality"] < 0 or normalized["materiality"] > 5:
        raise ValueError("materiality must be between 0 and 5.")
    if normalized["confidence"] < 1 or normalized["confidence"] > 5:
        raise ValueError("confidence must be between 1 and 5.")
    if not normalized["reasoning_short"]:
        raise ValueError("reasoning_short is empty.")
    return normalized


def estimate_cost_usd(
    input_tokens: int,
    output_tokens: int,
    input_cost_per_1m: float | None,
    output_cost_per_1m: float | None,
) -> float | str:
    if input_cost_per_1m is None or output_cost_per_1m is None:
        return ""
    input_cost = (input_tokens / 1_000_000.0) * input_cost_per_1m
    output_cost = (output_tokens / 1_000_000.0) * output_cost_per_1m
    return round(input_cost + output_cost, 8)


def build_messages(prompt_text: str, article_row: dict[str, Any]) -> list[dict[str, Any]]:
    cleaned_row = {}
    for key, value in article_row.items():
        cleaned_row[key] = "" if pd.isna(value) else value
    return [
        {
            "role": "system",
            "content": [{"type": "input_text", "text": prompt_text}],
        },
        {
            "role": "user",
            "content": [{"type": "input_text", "text": json.dumps(cleaned_row, ensure_ascii=False)}],
        },
    ]


def get_thread_session(pool_size: int) -> requests.Session:
    session = getattr(_THREAD_LOCAL, "session", None)
    if session is None:
        session = requests.Session()
        adapter = HTTPAdapter(pool_connections=pool_size, pool_maxsize=pool_size)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        _THREAD_LOCAL.session = session
    return session


def call_openai_responses_api(
    session: requests.Session,
    api_base: str,
    api_key: str,
    model: str,
    messages: list[dict[str, Any]],
    structured_output: bool,
    timeout_seconds: int,
    temperature: float,
) -> ClassificationResult:
    request_payload: dict[str, Any] = {
        "model": model,
        "input": messages,
        "temperature": temperature,
    }
    if structured_output:
        request_payload["text"] = {
            "format": {
                "type": "json_schema",
                "name": "news_spillover_classification",
                "schema": CLASSIFICATION_SCHEMA,
                "strict": True,
            }
        }

    response = session.post(
        f"{api_base.rstrip('/')}/responses",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=request_payload,
        timeout=timeout_seconds,
    )

    if response.status_code == 400 and structured_output:
        try:
            error_payload = response.json()
        except ValueError:
            error_payload = {"error": {"message": response.text[:500]}}
        raise StructuredOutputUnsupported(json.dumps(error_payload))

    if response.status_code in {408, 409, 429, 500, 502, 503, 504}:
        raise requests.HTTPError(response.text[:500], response=response)

    if response.status_code >= 400:
        raise OpenAIAPIError(response.text[:1000])

    raw_response = response.json()
    response_text = parse_response_text(raw_response)
    payload = normalize_payload(safe_json_loads(response_text))
    input_tokens, output_tokens = parse_usage(raw_response)
    return ClassificationResult(
        payload=payload,
        raw_response=raw_response,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def classify_with_retries(
    api_base: str,
    api_key: str,
    model: str,
    prompt_text: str,
    article_row: dict[str, Any],
    structured_mode: str,
    timeout_seconds: int,
    max_retries: int,
    temperature: float,
    pool_size: int,
) -> tuple[ClassificationResult, bool]:
    session = get_thread_session(pool_size)
    use_structured = structured_mode != "off"
    backoff = 1.0
    last_exception: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            result = call_openai_responses_api(
                session=session,
                api_base=api_base,
                api_key=api_key,
                model=model,
                messages=build_messages(prompt_text, article_row),
                structured_output=use_structured,
                timeout_seconds=timeout_seconds,
                temperature=temperature,
            )
            return result, use_structured
        except StructuredOutputUnsupported:
            if structured_mode == "on":
                raise
            use_structured = False
            last_exception = None
            continue
        except requests.RequestException as exc:
            last_exception = exc
            response = getattr(exc, "response", None)
            status_code = response.status_code if response is not None else None
            if status_code not in {408, 409, 429, 500, 502, 503, 504} or attempt >= max_retries:
                break
            time.sleep(backoff)
            backoff = min(backoff * 2, 15.0)
        except Exception as exc:
            last_exception = exc
            break

    if last_exception is None:
        last_exception = RuntimeError("Classification failed without a captured exception.")
    raise last_exception


def make_work_result(
    article_row: dict[str, Any],
    model: str,
    structured_mode: str,
    result: ClassificationResult | None,
    error: Exception | None,
    input_cost_per_1m: float | None,
    output_cost_per_1m: float | None,
    structured_used: bool,
) -> WorkResult:
    article_id = str(article_row["article_id"])
    classified_at = iso_utcnow()

    if result is not None:
        estimated_cost = estimate_cost_usd(
            result.input_tokens,
            result.output_tokens,
            input_cost_per_1m,
            output_cost_per_1m,
        )
        output_row = {
            **article_row,
            "classification_status": "success",
            **result.payload,
            "model": model,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "estimated_cost_usd": estimated_cost,
            "classified_at": classified_at,
        }
        raw_row = {
            "article_id": article_id,
            "classified_at": classified_at,
            "model": model,
            "structured_output": structured_used,
            "response": result.raw_response,
        }
        return WorkResult(
            article_id=article_id,
            output_row=output_row,
            raw_row=raw_row,
            success=True,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            estimated_cost=estimated_cost,
        )

    error_row = {
        **article_row,
        "classification_status": "error",
        "model": model,
        "classified_at": classified_at,
        "reasoning_short": f"error: {str(error)[:200]}",
    }
    raw_row = {
        "article_id": article_id,
        "classified_at": classified_at,
        "model": model,
        "structured_output": structured_mode != "off",
        "error": str(error),
    }
    return WorkResult(
        article_id=article_id,
        output_row=error_row,
        raw_row=raw_row,
        success=False,
        input_tokens=0,
        output_tokens=0,
        estimated_cost="",
    )


def worker_classify(
    article_row: dict[str, Any],
    api_base: str,
    api_key: str,
    model: str,
    prompt_text: str,
    structured_mode: str,
    timeout_seconds: int,
    max_retries: int,
    temperature: float,
    input_cost_per_1m: float | None,
    output_cost_per_1m: float | None,
    pool_size: int,
) -> WorkResult:
    try:
        result, structured_used = classify_with_retries(
            api_base=api_base,
            api_key=api_key,
            model=model,
            prompt_text=prompt_text,
            article_row=article_row,
            structured_mode=structured_mode,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            temperature=temperature,
            pool_size=pool_size,
        )
        return make_work_result(
            article_row=article_row,
            model=model,
            structured_mode=structured_mode,
            result=result,
            error=None,
            input_cost_per_1m=input_cost_per_1m,
            output_cost_per_1m=output_cost_per_1m,
            structured_used=structured_used,
        )
    except Exception as exc:
        return make_work_result(
            article_row=article_row,
            model=model,
            structured_mode=structured_mode,
            result=None,
            error=exc,
            input_cost_per_1m=input_cost_per_1m,
            output_cost_per_1m=output_cost_per_1m,
            structured_used=structured_mode != "off",
        )


def run_preflight(
    article_row: dict[str, Any],
    api_base: str,
    api_key: str,
    model: str,
    prompt_text: str,
    structured_output: str,
    timeout_seconds: int,
    max_retries: int,
    temperature: float,
    input_cost_per_1m: float | None,
    output_cost_per_1m: float | None,
    pool_size: int,
) -> tuple[WorkResult, str]:
    resolved_mode = structured_output
    work_result = worker_classify(
        article_row=article_row,
        api_base=api_base,
        api_key=api_key,
        model=model,
        prompt_text=prompt_text,
        structured_mode=resolved_mode,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        temperature=temperature,
        input_cost_per_1m=input_cost_per_1m,
        output_cost_per_1m=output_cost_per_1m,
        pool_size=pool_size,
    )

    if structured_output == "auto":
        if work_result.success and work_result.raw_row.get("structured_output") is False:
            resolved_mode = "off"
        elif not work_result.success:
            error_text = str(work_result.raw_row.get("error", ""))
            if "json_schema" in error_text or "Unsupported response format" in error_text:
                resolved_mode = "off"
    return work_result, resolved_mode


def main() -> int:
    load_dotenv()
    args = build_parser().parse_args()

    input_path = resolve_path(args.input)
    prompt_path = resolve_path(args.prompt_file)
    output_path = resolve_path(args.output)
    raw_output_path = resolve_path(args.raw_output) if args.raw_output else infer_raw_output_path(output_path)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    if args.concurrency <= 0:
        raise ValueError("--concurrency must be positive.")
    if args.sleep_seconds < 0:
        raise ValueError("--sleep-seconds cannot be negative.")

    model = args.model or os.environ.get("OPENAI_MODEL", "").strip()
    if not model:
        raise ValueError("No model configured. Set OPENAI_MODEL or pass --model.")

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set in the environment or .env.")

    api_base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()
    input_cost_per_1m = (
        args.input_cost_per_1m
        if args.input_cost_per_1m is not None
        else (
            float(os.environ["OPENAI_INPUT_COST_PER_1M_USD"])
            if os.environ.get("OPENAI_INPUT_COST_PER_1M_USD")
            else None
        )
    )
    output_cost_per_1m = (
        args.output_cost_per_1m
        if args.output_cost_per_1m is not None
        else (
            float(os.environ["OPENAI_OUTPUT_COST_PER_1M_USD"])
            if os.environ.get("OPENAI_OUTPUT_COST_PER_1M_USD")
            else None
        )
    )

    df = pd.read_csv(input_path)
    missing = [column for column in INPUT_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Missing required input columns: {missing}")

    prompt_text = read_text(prompt_path)
    existing_ids = load_existing_ids(output_path)
    ensure_csv_header(output_path)
    ensure_dir(raw_output_path.parent)

    remaining_df = df.loc[~df["article_id"].astype(str).isin(existing_ids), INPUT_COLUMNS].copy()
    if args.limit and args.limit > 0:
        remaining_df = remaining_df.head(args.limit)

    total_to_process = len(remaining_df)
    if total_to_process == 0:
        print("No new articles to classify. Output is already up to date.")
        return 0

    article_rows = remaining_df.to_dict(orient="records")
    resolved_structured_mode = args.structured_output
    processed = 0
    success_count = 0
    error_count = 0
    total_input_tokens = 0
    total_output_tokens = 0
    total_estimated_cost = 0.0

    print(
        f"Starting classification with concurrency={args.concurrency}, "
        f"structured_output={args.structured_output}, sleep_seconds={args.sleep_seconds}"
    )

    preflight_row = article_rows.pop(0)
    preflight_result, resolved_structured_mode = run_preflight(
        article_row=preflight_row,
        api_base=api_base,
        api_key=api_key,
        model=model,
        prompt_text=prompt_text,
        structured_output=args.structured_output,
        timeout_seconds=args.timeout_seconds,
        max_retries=args.max_retries,
        temperature=args.temperature,
        input_cost_per_1m=input_cost_per_1m,
        output_cost_per_1m=output_cost_per_1m,
        pool_size=max(16, args.concurrency * 2),
    )

    append_csv_row(output_path, preflight_result.output_row)
    append_jsonl_row(raw_output_path, preflight_result.raw_row)
    processed += 1
    if preflight_result.success:
        success_count += 1
        total_input_tokens += preflight_result.input_tokens
        total_output_tokens += preflight_result.output_tokens
        if isinstance(preflight_result.estimated_cost, float):
            total_estimated_cost += preflight_result.estimated_cost
    else:
        error_count += 1

    print(
        f"Preflight completed with structured_output={resolved_structured_mode}. "
        f"Processed {processed}/{total_to_process}."
    )

    if args.sleep_seconds > 0 and processed < total_to_process:
        time.sleep(args.sleep_seconds)

    if article_rows:
        pool_size = max(16, args.concurrency * 2)
        with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
            future_to_article_id: dict[Future[WorkResult], str] = {}
            row_iter = iter(article_rows)

            def submit_next() -> bool:
                try:
                    row = next(row_iter)
                except StopIteration:
                    return False
                future = executor.submit(
                    worker_classify,
                    row,
                    api_base,
                    api_key,
                    model,
                    prompt_text,
                    resolved_structured_mode,
                    args.timeout_seconds,
                    args.max_retries,
                    args.temperature,
                    input_cost_per_1m,
                    output_cost_per_1m,
                    pool_size,
                )
                future_to_article_id[future] = str(row["article_id"])
                return True

            for _ in range(min(args.concurrency, len(article_rows))):
                submit_next()

            while future_to_article_id:
                done, _ = wait(list(future_to_article_id.keys()), return_when=FIRST_COMPLETED)
                for future in done:
                    future_to_article_id.pop(future, None)
                    work_result = future.result()
                    append_csv_row(output_path, work_result.output_row)
                    append_jsonl_row(raw_output_path, work_result.raw_row)

                    processed += 1
                    if work_result.success:
                        success_count += 1
                        total_input_tokens += work_result.input_tokens
                        total_output_tokens += work_result.output_tokens
                        if isinstance(work_result.estimated_cost, float):
                            total_estimated_cost += work_result.estimated_cost
                    else:
                        error_count += 1

                    if processed % 25 == 0 or processed == total_to_process:
                        print(
                            f"Processed {processed}/{total_to_process} new articles "
                            f"(success={success_count}, error={error_count}, "
                            f"input_tokens={total_input_tokens}, output_tokens={total_output_tokens}, "
                            f"estimated_cost_usd={total_estimated_cost:.6f})"
                        )

                    if args.sleep_seconds > 0 and processed < total_to_process:
                        time.sleep(args.sleep_seconds)

                    submit_next()

    print("\nClassification run completed.")
    print(f"Output CSV: {output_path}")
    print(f"Raw JSONL: {raw_output_path}")
    print(f"Success rows: {success_count}")
    print(f"Error rows: {error_count}")
    print(f"Total input tokens: {total_input_tokens}")
    print(f"Total output tokens: {total_output_tokens}")
    if input_cost_per_1m is not None and output_cost_per_1m is not None:
        print(f"Estimated cost (USD): {total_estimated_cost:.6f}")
    else:
        print(
            "Estimated cost (USD): unavailable; set OPENAI_INPUT_COST_PER_1M_USD and "
            "OPENAI_OUTPUT_COST_PER_1M_USD or pass CLI overrides."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
