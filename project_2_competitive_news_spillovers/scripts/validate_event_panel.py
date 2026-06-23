"""Validate the final competitor event panel and write report-friendly diagnostics."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from utils import ensure_dir, load_ticker_config, resolve_path


LLM_DEFAULT = (
    "data/processed/llm_output/llm_classifications_sample_n50_per_stratum_max1500_final.csv"
)
PANEL_DEFAULT = "data/processed/news_competitor_event_panel.csv"
CONFIG_DEFAULT = "config/competitor_groups.yaml"
RETURNS_DEFAULT = "data/interim/daily_returns.csv"
SUMMARY_DEFAULT = "outputs/tables/event_panel_validation_summary.csv"
MARKDOWN_DEFAULT = "outputs/analysis/event_panel_validation.md"
COMPETITOR_OUTCOME_COLUMNS = [
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
]
DATE_COLUMNS = ["published_date", "event_trade_date", "t0_date", "t1_date", "t2_date", "t3_date"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate the final event-study panel.")
    parser.add_argument("--panel", default=PANEL_DEFAULT, help="Path to the final event panel CSV.")
    parser.add_argument("--llm", default=LLM_DEFAULT, help="Path to the final LLM classification CSV.")
    parser.add_argument(
        "--config",
        default=CONFIG_DEFAULT,
        help="Path to the competitor group configuration file.",
    )
    parser.add_argument(
        "--returns",
        default=RETURNS_DEFAULT,
        help="Path to the daily returns file used to derive trading windows.",
    )
    parser.add_argument(
        "--summary-output",
        default=SUMMARY_DEFAULT,
        help="CSV output path for validation diagnostics.",
    )
    parser.add_argument(
        "--markdown-output",
        default=MARKDOWN_DEFAULT,
        help="Markdown output path for the human-readable validation summary.",
    )
    return parser


def to_bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin(["true", "1", "yes"])


def build_ticker_to_group(config: dict[str, Any]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for group_name, payload in config.get("industries", {}).items():
        if not isinstance(payload, dict):
            continue
        for ticker in payload.get("tickers", []):
            ticker_text = str(ticker).strip().upper()
            if ticker_text:
                mapping[ticker_text] = str(group_name)
    return mapping


def add_check(
    rows: list[dict[str, object]],
    check_name: str,
    status: str,
    value: int | float | str,
    detail: str,
) -> None:
    rows.append(
        {
            "section": "check",
            "item": check_name,
            "subgroup": "",
            "status": status,
            "value": value,
            "detail": detail,
        }
    )


def count_missing_by_ticker(panel: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for ticker, ticker_df in panel.groupby("competitor_ticker"):
        missing_total = int(ticker_df[COMPETITOR_OUTCOME_COLUMNS].isna().sum().sum())
        rows.append(
            {
                "section": "missing_by_ticker",
                "item": ticker,
                "subgroup": "all_competitor_outcomes",
                "status": "",
                "value": missing_total,
                "detail": f"Total missing competitor outcome values across {len(COMPETITOR_OUTCOME_COLUMNS)} columns.",
            }
        )
    return pd.DataFrame(rows).sort_values(["value", "item"], ascending=[False, True])


def count_missing_by_outcome(panel: pd.DataFrame) -> pd.DataFrame:
    rows = [
        {
            "section": "missing_by_outcome",
            "item": column,
            "subgroup": "",
            "status": "",
            "value": int(panel[column].isna().sum()),
            "detail": "Missing values across all panel rows.",
        }
        for column in COMPETITOR_OUTCOME_COLUMNS
    ]
    return pd.DataFrame(rows).sort_values(["value", "item"], ascending=[False, True])


def build_markdown_summary(
    check_rows: pd.DataFrame,
    sample_rows: pd.DataFrame,
    missing_by_ticker: pd.DataFrame,
    missing_by_outcome: pd.DataFrame,
) -> str:
    failing = check_rows.loc[check_rows["status"] == "fail", "item"].tolist()
    warning = check_rows.loc[check_rows["status"] == "warn", "item"].tolist()

    lines = [
        "# Event Panel Validation",
        "",
        "## Overall status",
        "",
        f"- Failing checks: {len(failing)}.",
        f"- Warning checks: {len(warning)}.",
        f"- Passing checks: {int((check_rows['status'] == 'pass').sum())}.",
        "",
        "## Check results",
        "",
    ]

    for row in check_rows.itertuples(index=False):
        lines.append(f"- `{row.item}`: {row.status} ({row.value}). {row.detail}")

    lines.extend(
        [
            "",
            "## Sample counts",
            "",
        ]
    )
    for row in sample_rows.itertuples(index=False):
        lines.append(f"- `{row.item}`: {int(row.value):,} rows. {row.detail}")

    lines.extend(
        [
            "",
            "## Missing competitor outcomes by ticker",
            "",
        ]
    )
    for row in missing_by_ticker.head(10).itertuples(index=False):
        lines.append(f"- `{row.item}`: {int(row.value):,} missing values.")

    lines.extend(
        [
            "",
            "## Missing competitor outcomes by variable",
            "",
        ]
    )
    for row in missing_by_outcome.itertuples(index=False):
        lines.append(f"- `{row.item}`: {int(row.value):,} missing values.")

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- The requested CAR identity checks were mapped to the abnormal-return CAR columns (`competitor_car_abret_spy_0_1` and `competitor_car_abret_spy_1_3`) because those are the fields that correspond to the abnormal-return components named in the request.",
            "- The raw-return CAR columns (`competitor_car_0_1` and `competitor_car_1_3`) were also checked against their raw return components.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = build_parser().parse_args()

    panel_path = resolve_path(args.panel)
    llm_path = resolve_path(args.llm)
    config_path = resolve_path(args.config)
    returns_path = resolve_path(args.returns)
    summary_output = resolve_path(args.summary_output)
    markdown_output = resolve_path(args.markdown_output)

    for path in [panel_path, llm_path, config_path, returns_path]:
        if not path.exists():
            raise FileNotFoundError(f"Required input not found: {path}")

    panel = pd.read_csv(panel_path)
    llm = pd.read_csv(llm_path)
    returns = pd.read_csv(returns_path)
    config = load_ticker_config(config_path)

    for column in ["sample_broad", "sample_strict", "sample_very_strict"]:
        panel[column] = to_bool(panel[column])
    llm = llm.loc[llm["classification_status"] == "success"].copy()

    for column in DATE_COLUMNS:
        panel[column] = pd.to_datetime(panel[column], errors="coerce")

    ticker_to_group = build_ticker_to_group(config)
    panel["source_group_from_config"] = panel["source_ticker"].astype(str).str.upper().map(ticker_to_group)
    panel["competitor_group_from_config"] = panel["competitor_ticker"].astype(str).str.upper().map(ticker_to_group)

    allowed_strata = set(llm["stratum"].dropna().astype(str).unique())
    panel_strata = set(panel["stratum"].dropna().astype(str).unique())

    check_rows: list[dict[str, object]] = []
    sample_rows: list[dict[str, object]] = []

    self_rows = int((panel["source_ticker"] == panel["competitor_ticker"]).sum())
    add_check(
        check_rows,
        "source_ticker_not_equal_competitor_ticker",
        "pass" if self_rows == 0 else "fail",
        self_rows,
        "Rows where `source_ticker == competitor_ticker`.",
    )

    same_group_mask = (
        panel["source_group_from_config"].notna()
        & panel["competitor_group_from_config"].notna()
        & (panel["source_group_from_config"] == panel["competitor_group_from_config"])
        & (panel["source_group"] == panel["source_group_from_config"])
        & (panel["competitor_group"] == panel["competitor_group_from_config"])
    )
    group_violations = int((~same_group_mask).sum())
    add_check(
        check_rows,
        "source_and_competitor_same_config_group",
        "pass" if group_violations == 0 else "fail",
        group_violations,
        "Rows where source/competitor group assignments disagree with `config/competitor_groups.yaml`.",
    )

    strata_ok = len(allowed_strata) == 25 and panel_strata == allowed_strata
    old_strata_count = len(panel_strata - allowed_strata)
    add_check(
        check_rows,
        "broad_25_strata_only",
        "pass" if strata_ok else "fail",
        old_strata_count,
        f"Panel strata count={len(panel_strata)}; allowed strata count from final LLM file={len(allowed_strata)}.",
    )

    nonmissing_order_mask = panel[DATE_COLUMNS].notna().all(axis=1)
    order_violations = int(
        (
            ~(
                (panel.loc[nonmissing_order_mask, "published_date"] <= panel.loc[nonmissing_order_mask, "event_trade_date"])
                & (panel.loc[nonmissing_order_mask, "event_trade_date"] <= panel.loc[nonmissing_order_mask, "t0_date"])
                & (panel.loc[nonmissing_order_mask, "t0_date"] < panel.loc[nonmissing_order_mask, "t1_date"])
                & (panel.loc[nonmissing_order_mask, "t1_date"] < panel.loc[nonmissing_order_mask, "t2_date"])
                & (panel.loc[nonmissing_order_mask, "t2_date"] < panel.loc[nonmissing_order_mask, "t3_date"])
            )
        ).sum()
    )
    missing_window_dates = int((~nonmissing_order_mask).sum())
    date_status = "pass" if order_violations == 0 and missing_window_dates == 0 else "warn"
    date_detail = (
        f"Rows with true ordering violations among fully observed dates={order_violations}; "
        f"rows missing one or more window dates={missing_window_dates}."
    )
    add_check(
        check_rows,
        "date_window_ordering",
        date_status,
        order_violations + missing_window_dates,
        date_detail,
    )

    returns["date"] = pd.to_datetime(returns["date"], errors="coerce")
    spy_dates = sorted(returns.loc[returns["ticker"] == "SPY", "date"].dropna().drop_duplicates().tolist())
    spy_index = {date_value: index for index, date_value in enumerate(spy_dates)}
    t1_rows = panel.loc[panel["event_trade_date"].notna() & panel["t1_date"].notna(), ["event_trade_date", "t1_date"]]
    t1_violations = 0
    for row in t1_rows.itertuples(index=False):
        event_idx = spy_index.get(row.event_trade_date)
        t1_idx = spy_index.get(row.t1_date)
        if event_idx is None or t1_idx is None or t1_idx != event_idx + 1:
            t1_violations += 1
    add_check(
        check_rows,
        "t1_is_next_trading_day_after_event_trade_date",
        "pass" if t1_violations == 0 else "fail",
        t1_violations,
        "Rows where `t1_date` is not exactly the next SPY trading day after `event_trade_date`.",
    )

    abnormal_car01_expected = panel["competitor_abret_spy_t0"] + panel["competitor_abret_spy_t1"]
    abnormal_car13_expected = (
        panel["competitor_abret_spy_t1"] + panel["competitor_abret_spy_t2"] + panel["competitor_abret_spy_t3"]
    )
    abnormal_car01_mismatches = int(
        (
            ~np.isclose(
                panel["competitor_car_abret_spy_0_1"],
                abnormal_car01_expected,
                equal_nan=True,
                atol=1e-10,
                rtol=1e-10,
            )
        ).sum()
    )
    abnormal_car13_mismatches = int(
        (
            ~np.isclose(
                panel["competitor_car_abret_spy_1_3"],
                abnormal_car13_expected,
                equal_nan=True,
                atol=1e-10,
                rtol=1e-10,
            )
        ).sum()
    )
    add_check(
        check_rows,
        "abnormal_car_0_1_identity",
        "pass" if abnormal_car01_mismatches == 0 else "fail",
        abnormal_car01_mismatches,
        "Rows where `competitor_car_abret_spy_0_1` does not equal `competitor_abret_spy_t0 + competitor_abret_spy_t1`.",
    )
    add_check(
        check_rows,
        "abnormal_car_1_3_identity",
        "pass" if abnormal_car13_mismatches == 0 else "fail",
        abnormal_car13_mismatches,
        "Rows where `competitor_car_abret_spy_1_3` does not equal `competitor_abret_spy_t1 + t2 + t3`.",
    )

    raw_car01_expected = panel["competitor_ret_t0"] + panel["competitor_ret_t1"]
    raw_car13_expected = panel["competitor_ret_t1"] + panel["competitor_ret_t2"] + panel["competitor_ret_t3"]
    raw_car01_mismatches = int(
        (
            ~np.isclose(
                panel["competitor_car_0_1"],
                raw_car01_expected,
                equal_nan=True,
                atol=1e-10,
                rtol=1e-10,
            )
        ).sum()
    )
    raw_car13_mismatches = int(
        (
            ~np.isclose(
                panel["competitor_car_1_3"],
                raw_car13_expected,
                equal_nan=True,
                atol=1e-10,
                rtol=1e-10,
            )
        ).sum()
    )
    add_check(
        check_rows,
        "raw_car_columns_identity",
        "pass" if raw_car01_mismatches == 0 and raw_car13_mismatches == 0 else "fail",
        raw_car01_mismatches + raw_car13_mismatches,
        f"Rows failing raw CAR identities: 0_1={raw_car01_mismatches}, 1_3={raw_car13_mismatches}.",
    )

    duplicates = int(panel.duplicated(["article_id", "source_ticker", "competitor_ticker"]).sum())
    add_check(
        check_rows,
        "duplicate_article_source_competitor_rows",
        "pass" if duplicates == 0 else "fail",
        duplicates,
        "Duplicate rows by `article_id + source_ticker + competitor_ticker`.",
    )

    strict_expected = panel["sample_broad"] & (panel["relevance_type"] != "market_roundup_but_relevant")
    very_strict_expected = strict_expected & (
        pd.to_numeric(panel["materiality"], errors="coerce") >= 3
    ) & (pd.to_numeric(panel["confidence"], errors="coerce") >= 4)
    broad_flag_violations = int((~panel["sample_broad"]).sum())
    strict_flag_violations = int((panel["sample_strict"] != strict_expected).sum())
    very_strict_flag_violations = int((panel["sample_very_strict"] != very_strict_expected).sum())
    sample_status = (
        "pass"
        if broad_flag_violations == 0 and strict_flag_violations == 0 and very_strict_flag_violations == 0
        else "fail"
    )
    add_check(
        check_rows,
        "sample_flag_consistency",
        sample_status,
        broad_flag_violations + strict_flag_violations + very_strict_flag_violations,
        (
            f"Flag mismatches: broad={broad_flag_violations}, strict={strict_flag_violations}, "
            f"very_strict={very_strict_flag_violations}."
        ),
    )

    for item, value, detail in [
        ("sample_broad_rows", int(panel["sample_broad"].sum()), "All relevant rows in the panel."),
        (
            "sample_strict_rows",
            int(panel["sample_strict"].sum()),
            "Rows excluding `market_roundup_but_relevant`.",
        ),
        (
            "sample_very_strict_rows",
            int(panel["sample_very_strict"].sum()),
            "Strict rows with `materiality >= 3` and `confidence >= 4`.",
        ),
    ]:
        sample_rows.append(
            {
                "section": "sample_count",
                "item": item,
                "subgroup": "",
                "status": "info",
                "value": value,
                "detail": detail,
            }
        )

    check_df = pd.DataFrame(check_rows)
    sample_df = pd.DataFrame(sample_rows)
    missing_ticker_df = count_missing_by_ticker(panel)
    missing_outcome_df = count_missing_by_outcome(panel)

    combined_summary = pd.concat(
        [check_df, sample_df, missing_ticker_df, missing_outcome_df],
        ignore_index=True,
    )
    combined_summary = combined_summary[
        ["section", "item", "subgroup", "status", "value", "detail"]
    ]

    markdown = build_markdown_summary(check_df, sample_df, missing_ticker_df, missing_outcome_df)

    ensure_dir(summary_output.parent)
    ensure_dir(markdown_output.parent)
    combined_summary.to_csv(summary_output, index=False)
    with markdown_output.open("w", encoding="utf-8") as handle:
        handle.write(markdown)

    print("Event panel validation completed.")
    print(f"Panel: {panel_path}")
    print(f"Validation summary CSV: {summary_output}")
    print(f"Validation markdown: {markdown_output}")
    print(f"Failing checks: {int((check_df['status'] == 'fail').sum())}")
    print(f"Warning checks: {int((check_df['status'] == 'warn').sum())}")
    print(f"Broad sample rows: {int(panel['sample_broad'].sum()):,}")
    print(f"Strict sample rows: {int(panel['sample_strict'].sum()):,}")
    print(f"Very strict sample rows: {int(panel['sample_very_strict'].sum()):,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
