"""Build balanced LLM input samples from article strata."""

from __future__ import annotations

import argparse
import random

import pandas as pd

from utils import ensure_dir, resolve_path


OUTPUT_COLUMNS = [
    "article_id",
    "published_date",
    "title",
    "summary",
    "publisher",
    "linked_ticker_count",
    "linked_tickers",
    "stratum",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a balanced LLM classification sample.")
    parser.add_argument(
        "--input",
        default="data/interim/news_articles_with_strata.csv",
        help="Input article dataset with strata.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional output CSV path. Defaults to a per-stratum filename under data/processed/llm_input/.",
    )
    parser.add_argument(
        "--per-stratum",
        type=int,
        required=True,
        help="Maximum number of rows to sample per stratum.",
    )
    parser.add_argument(
        "--max-total-rows",
        type=int,
        default=0,
        help="Optional cap on total sample rows across all strata. If omitted, all per-stratum samples are kept.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for deterministic balanced sampling.",
    )
    return parser


def infer_output_path(per_stratum: int, max_total_rows: int) -> str:
    filename = f"data/processed/llm_input/llm_input_sample_n{per_stratum}_per_stratum"
    if max_total_rows > 0:
        filename += f"_max{max_total_rows}"
    filename += ".csv"
    return filename


def allocate_evenly(available_counts: dict[str, int], total_target: int, seed: int) -> dict[str, int]:
    if total_target <= 0:
        return {stratum: 0 for stratum in available_counts}

    strata = [stratum for stratum, count in available_counts.items() if count > 0]
    rng = random.Random(seed)
    rng.shuffle(strata)

    allocation = {stratum: 0 for stratum in available_counts}
    remaining = total_target

    while remaining > 0 and strata:
        progressed = False
        next_round: list[str] = []
        for stratum in strata:
            if remaining <= 0:
                break
            if allocation[stratum] < available_counts[stratum]:
                allocation[stratum] += 1
                remaining -= 1
                progressed = True
            if allocation[stratum] < available_counts[stratum]:
                next_round.append(stratum)
        if not progressed:
            break
        strata = next_round

    return allocation


def main() -> int:
    args = build_parser().parse_args()

    input_path = resolve_path(args.input)
    output_path = resolve_path(args.output) if args.output else resolve_path(
        infer_output_path(args.per_stratum, args.max_total_rows)
    )

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    if args.per_stratum <= 0:
        raise ValueError("--per-stratum must be positive.")
    if args.max_total_rows < 0:
        raise ValueError("--max-total-rows cannot be negative.")

    df = pd.read_csv(input_path)
    missing = [column for column in OUTPUT_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in input: {missing}")

    strata = sorted(df["stratum"].dropna().unique())
    if not strata:
        raise ValueError("Input file contains no non-empty strata.")

    per_stratum_frames: dict[str, pd.DataFrame] = {}
    available_counts: dict[str, int] = {}
    for index, stratum in enumerate(strata):
        subset = df.loc[df["stratum"] == stratum, OUTPUT_COLUMNS].sort_values(
            ["published_date", "article_id"]
        )
        take_n = min(args.per_stratum, len(subset))
        sampled = subset.sample(n=take_n, random_state=args.seed + index) if take_n else subset.iloc[0:0]
        per_stratum_frames[stratum] = sampled
        available_counts[stratum] = len(sampled)

    if args.max_total_rows > 0:
        total_target = min(args.max_total_rows, sum(available_counts.values()))
        final_counts = allocate_evenly(available_counts, total_target, args.seed + 10_000)
    else:
        final_counts = available_counts

    sampled_frames: list[pd.DataFrame] = []
    for stratum in strata:
        sampled = per_stratum_frames[stratum]
        take_n = final_counts.get(stratum, 0)
        if take_n <= 0:
            continue
        if take_n == len(sampled):
            sampled_frames.append(sampled)
        else:
            sampled_frames.append(sampled.sample(n=take_n, random_state=args.seed + 20_000 + strata.index(stratum)))

    sample = (
        pd.concat(sampled_frames, ignore_index=True)
        .sort_values(["stratum", "published_date", "article_id"])
        .reset_index(drop=True)
    )

    ensure_dir(output_path.parent)
    sample.to_csv(output_path, index=False)

    print("Balanced LLM sample created.")
    print(f"Input: {input_path}")
    print(f"Output: {output_path}")
    print(f"Detected strata: {len(strata):,}")
    print(f"Rows: {len(sample):,}")
    if args.max_total_rows > 0:
        print(f"Total-row cap: {args.max_total_rows:,}")
    print("\nRows per stratum:")
    print(sample["stratum"].value_counts().sort_index().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
