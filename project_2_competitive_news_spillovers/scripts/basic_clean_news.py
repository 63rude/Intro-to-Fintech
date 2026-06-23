"""
Basic conservative cleaning for Project 2 news data.

This script does NOT do semantic/content filtering.
It only removes:
- rows with missing core fields;
- rows with empty / extremely short summaries;
- obvious technical junk like "#NAME?";
- exact duplicates by ticker+url;
- exact duplicates by ticker+title+date.

Input:
    data/interim/news_normalized.csv

Outputs:
    data/interim/news_basic_clean.csv
    data/interim/news_basic_removed.csv
    outputs/samples/news_basic_clean_sample_200.csv
    outputs/samples/news_basic_removed_sample_200.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def norm_text(series: pd.Series) -> pd.Series:
    return (
        series.fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
        .str.replace(r"\s+", " ", regex=True)
    )


def add_remove_reason(mask: pd.Series, reason: str, reasons: pd.Series) -> pd.Series:
    reasons.loc[mask & (reasons == "")] = reason
    reasons.loc[mask & (reasons != reason) & (~reasons.str.contains(reason, regex=False))] = (
        reasons.loc[mask & (reasons != reason) & (~reasons.str.contains(reason, regex=False))]
        + "; "
        + reason
    )
    return reasons


def main() -> None:
    parser = argparse.ArgumentParser(description="Basic conservative cleaning for normalized news.")
    parser.add_argument(
        "--input",
        default="data/interim/news_normalized.csv",
        help="Input normalized news CSV.",
    )
    parser.add_argument(
        "--output",
        default="data/interim/news_basic_clean.csv",
        help="Output cleaned candidate CSV.",
    )
    parser.add_argument(
        "--removed-output",
        default="data/interim/news_basic_removed.csv",
        help="Output removed rows CSV.",
    )
    parser.add_argument(
        "--min-summary-len",
        type=int,
        default=30,
        help="Minimum summary length. Use 0 to keep title-only rows.",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=200,
        help="Sample size for quick manual inspection.",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    removed_output_path = Path(args.removed_output)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    df = pd.read_csv(input_path)
    original_rows = len(df)

    required_cols = ["query_ticker", "published_date", "title", "summary", "url"]
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")

    # Helper columns.
    df["_title_norm"] = norm_text(df["title"])
    df["_summary_norm"] = norm_text(df["summary"])
    df["_url_norm"] = norm_text(df["url"])
    df["_ticker_norm"] = norm_text(df["query_ticker"])
    df["_date_norm"] = norm_text(df["published_date"])

    df["title_len"] = df["title"].fillna("").astype(str).str.len()
    df["summary_len"] = df["summary"].fillna("").astype(str).str.len()
    df["text_len"] = df["title_len"] + df["summary_len"]

    remove_reason = pd.Series([""] * len(df), index=df.index, dtype="object")

    # Hard technical filters only.
    missing_ticker = df["_ticker_norm"].eq("")
    missing_date = df["_date_norm"].eq("")
    missing_title = df["_title_norm"].eq("")
    missing_url = df["_url_norm"].eq("")
    missing_summary = df["_summary_norm"].eq("")
    short_summary = df["summary_len"] < args.min_summary_len

    # Obvious spreadsheet/API junk.
    technical_junk = (
        df["_title_norm"].isin(["#name?", "nan", "none", "null"])
        | df["_summary_norm"].isin(["#name?", "nan", "none", "null"])
    )

    remove_reason = add_remove_reason(missing_ticker, "missing_ticker", remove_reason)
    remove_reason = add_remove_reason(missing_date, "missing_date", remove_reason)
    remove_reason = add_remove_reason(missing_title, "missing_title", remove_reason)
    remove_reason = add_remove_reason(missing_url, "missing_url", remove_reason)
    remove_reason = add_remove_reason(missing_summary, "missing_summary", remove_reason)

    if args.min_summary_len > 0:
        remove_reason = add_remove_reason(
            short_summary & ~missing_summary,
            f"summary_len_below_{args.min_summary_len}",
            remove_reason,
        )

    remove_reason = add_remove_reason(technical_junk, "technical_junk", remove_reason)

    # Duplicates.
    # Keep the first occurrence because it preserves one usable event row.
    dup_ticker_url = df.duplicated(subset=["_ticker_norm", "_url_norm"], keep="first")
    dup_ticker_title_date = df.duplicated(
        subset=["_ticker_norm", "_title_norm", "_date_norm"],
        keep="first",
    )

    remove_reason = add_remove_reason(dup_ticker_url, "duplicate_ticker_url", remove_reason)
    remove_reason = add_remove_reason(
        dup_ticker_title_date,
        "duplicate_ticker_title_date",
        remove_reason,
    )

    df["basic_filter_reason"] = remove_reason
    df["basic_filter_status"] = df["basic_filter_reason"].apply(
        lambda x: "keep" if x == "" else "drop"
    )

    removed = df[df["basic_filter_status"] == "drop"].copy()
    clean = df[df["basic_filter_status"] == "keep"].copy()

    # Remove internal helper columns but keep useful audit columns.
    helper_cols = ["_title_norm", "_summary_norm", "_url_norm", "_ticker_norm", "_date_norm"]
    clean = clean.drop(columns=helper_cols)
    removed = removed.drop(columns=helper_cols)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    removed_output_path.parent.mkdir(parents=True, exist_ok=True)

    clean.to_csv(output_path, index=False)
    removed.to_csv(removed_output_path, index=False)

    samples_dir = Path("outputs/samples")
    samples_dir.mkdir(parents=True, exist_ok=True)

    if len(clean) > 0:
        clean.sample(min(args.sample_size, len(clean)), random_state=1).to_csv(
            samples_dir / "news_basic_clean_sample_200.csv",
            index=False,
        )

    if len(removed) > 0:
        removed.sample(min(args.sample_size, len(removed)), random_state=1).to_csv(
            samples_dir / "news_basic_removed_sample_200.csv",
            index=False,
        )

    print("\nBasic news cleaning completed.")
    print(f"Input rows:              {original_rows:,}")
    print(f"Kept rows:               {len(clean):,}")
    print(f"Removed rows:            {len(removed):,}")
    print(f"Output clean file:       {output_path}")
    print(f"Output removed file:     {removed_output_path}")

    print("\nRemoval reasons:")
    if len(removed) > 0:
        reason_counts = (
            removed["basic_filter_reason"]
            .str.get_dummies(sep="; ")
            .sum()
            .sort_values(ascending=False)
        )
        print(reason_counts.to_string())
    else:
        print("No rows removed.")

    print("\nKept rows by ticker:")
    print(clean.groupby("query_ticker").size().sort_values(ascending=False).to_string())

    print("\nKept rows by publisher:")
    print(clean["publisher"].value_counts().head(20).to_string())


if __name__ == "__main__":
    main()