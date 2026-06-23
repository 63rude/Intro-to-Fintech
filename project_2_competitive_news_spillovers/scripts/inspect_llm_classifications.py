"""Inspect and summarize LLM news classifications."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from utils import ensure_dir, resolve_path


BASE_COLUMNS = [
    "article_id",
    "published_date",
    "publisher",
    "linked_ticker_count",
    "linked_tickers",
    "stratum",
    "title",
    "summary",
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
    "estimated_cost_usd",
    "classified_at",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect LLM classification outputs.")
    parser.add_argument(
        "--input",
        default="data/processed/llm_output/llm_classifications_sample_n20_per_stratum.csv",
        help="Input classification CSV.",
    )
    parser.add_argument(
        "--summary-output",
        default="outputs/tables/llm_classification_summary.csv",
        help="Summary CSV output path.",
    )
    parser.add_argument(
        "--relevant-output",
        default="outputs/samples/llm_relevant_sample_100.csv",
        help="Output path for relevant sample rows.",
    )
    parser.add_argument(
        "--not-relevant-output",
        default="outputs/samples/llm_not_relevant_sample_100.csv",
        help="Output path for not-relevant sample rows.",
    )
    parser.add_argument(
        "--low-confidence-output",
        default="outputs/samples/llm_low_confidence_sample_100.csv",
        help="Output path for low-confidence sample rows.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for sampled output files.",
    )
    return parser


def summarize_counts(df: pd.DataFrame, summary_type: str, group_cols: list[str]) -> pd.DataFrame:
    counts = df.groupby(group_cols, dropna=False).size().reset_index(name="count")
    counts["summary_type"] = summary_type
    total = counts["count"].sum()
    counts["share"] = counts["count"] / total if total else 0.0
    return counts


def summarize_by_stratum(df: pd.DataFrame, column_name: str) -> pd.DataFrame:
    counts = df.groupby(["stratum", column_name], dropna=False).size().reset_index(name="count")
    counts["summary_type"] = f"{column_name}_by_stratum"
    counts["share_within_stratum"] = counts.groupby("stratum")["count"].transform(
        lambda series: series / series.sum() if series.sum() else 0.0
    )
    return counts


def sample_rows(df: pd.DataFrame, n: int, seed: int) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    take_n = min(n, len(df))
    return df.sample(n=take_n, random_state=seed).sort_values(["stratum", "published_date", "article_id"])


def main() -> int:
    args = build_parser().parse_args()

    input_path = resolve_path(args.input)
    summary_output = resolve_path(args.summary_output)
    relevant_output = resolve_path(args.relevant_output)
    not_relevant_output = resolve_path(args.not_relevant_output)
    low_confidence_output = resolve_path(args.low_confidence_output)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    df = pd.read_csv(input_path)
    missing = [column for column in BASE_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in input: {missing}")

    df["is_relevant"] = df["is_relevant"].astype(str).str.lower()
    df["confidence"] = pd.to_numeric(df["confidence"], errors="coerce")
    df["materiality"] = pd.to_numeric(df["materiality"], errors="coerce")
    df["estimated_cost_usd"] = pd.to_numeric(df["estimated_cost_usd"], errors="coerce").fillna(0.0)

    success_df = df.loc[df["classification_status"] == "success"].copy()
    error_count = int((df["classification_status"] == "error").sum())
    total_estimated_cost = float(df["estimated_cost_usd"].sum())

    summary_frames = [
        summarize_counts(success_df, "relevance_distribution", ["is_relevant", "relevance_type"]),
        summarize_by_stratum(success_df, "relevance_type"),
        summarize_counts(success_df, "event_type_distribution", ["event_type"]),
        summarize_counts(success_df, "news_scope_distribution", ["news_scope"]),
        summarize_counts(
            success_df,
            "expected_competitor_effect_distribution",
            ["expected_competitor_effect"],
        ),
        summarize_counts(success_df, "materiality_distribution", ["materiality"]),
        summarize_counts(success_df, "confidence_distribution", ["confidence"]),
    ]

    headline_summary = pd.DataFrame(
        [
            {
                "summary_type": "run_totals",
                "metric": "total_rows",
                "value": len(df),
                "share": "",
            },
            {
                "summary_type": "run_totals",
                "metric": "successful_rows",
                "value": len(success_df),
                "share": "",
            },
            {
                "summary_type": "run_totals",
                "metric": "error_rows",
                "value": error_count,
                "share": "",
            },
            {
                "summary_type": "run_totals",
                "metric": "total_estimated_cost_usd",
                "value": round(total_estimated_cost, 8),
                "share": "",
            },
        ]
    )

    normalized_frames: list[pd.DataFrame] = [headline_summary]
    for frame in summary_frames:
        normalized_frames.append(frame)

    summary = pd.concat(normalized_frames, ignore_index=True, sort=False)

    relevant_sample = sample_rows(success_df.loc[success_df["is_relevant"] == "true", BASE_COLUMNS], 100, args.seed)
    not_relevant_sample = sample_rows(
        success_df.loc[success_df["is_relevant"] == "false", BASE_COLUMNS], 100, args.seed + 1
    )
    low_confidence_pool = success_df.sort_values(
        ["confidence", "materiality", "published_date", "article_id"],
        ascending=[True, False, True, True],
    )
    low_confidence_sample = low_confidence_pool.head(min(100, len(low_confidence_pool)))[BASE_COLUMNS]

    ensure_dir(summary_output.parent)
    ensure_dir(relevant_output.parent)
    ensure_dir(not_relevant_output.parent)
    ensure_dir(low_confidence_output.parent)

    summary.to_csv(summary_output, index=False)
    relevant_sample.to_csv(relevant_output, index=False)
    not_relevant_sample.to_csv(not_relevant_output, index=False)
    low_confidence_sample.to_csv(low_confidence_output, index=False)

    print("LLM classification inspection completed.")
    print(f"Input: {input_path}")
    print(f"Summary: {summary_output}")
    print(f"Relevant sample: {relevant_output}")
    print(f"Not relevant sample: {not_relevant_output}")
    print(f"Low confidence sample: {low_confidence_output}")

    print("\nTotal classified rows:")
    print(f"  total_rows={len(df):,}")
    print(f"  successful_rows={len(success_df):,}")
    print(f"  error_rows={error_count:,}")
    print(f"  total_estimated_cost_usd={total_estimated_cost:.6f}")

    print("\nRelevance distribution:")
    print(success_df[["is_relevant", "relevance_type"]].value_counts(dropna=False).to_string())

    print("\nRelevance by stratum:")
    relevance_by_stratum = (
        success_df.groupby(["stratum", "relevance_type"]).size().reset_index(name="count")
    )
    print(relevance_by_stratum.to_string(index=False))

    print("\nEvent type distribution:")
    print(success_df["event_type"].value_counts(dropna=False).to_string())

    print("\nNews scope distribution:")
    print(success_df["news_scope"].value_counts(dropna=False).to_string())

    print("\nExpected competitor effect distribution:")
    print(success_df["expected_competitor_effect"].value_counts(dropna=False).to_string())

    print("\nMateriality distribution:")
    print(success_df["materiality"].value_counts(dropna=False).sort_index().to_string())

    print("\nConfidence distribution:")
    print(success_df["confidence"].value_counts(dropna=False).sort_index().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
