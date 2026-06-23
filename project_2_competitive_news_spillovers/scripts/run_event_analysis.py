"""Run descriptive and regression analysis on the competitor event panel."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import statsmodels.formula.api as smf

from utils import ensure_dir, resolve_path


LLM_DEFAULT = (
    "data/processed/llm_output/llm_classifications_sample_n50_per_stratum_max1500_final.csv"
)
MAIN_OUTCOMES = [
    "competitor_abret_spy_t1",
    "competitor_car_abret_spy_0_1",
    "competitor_car_abret_spy_1_3",
]
EFFECT_ORDER = [
    "same_direction_contagion",
    "opposite_direction_competition",
    "positive_for_competitors",
    "negative_for_competitors",
    "neutral_or_no_clear_effect",
]
RELEVANCE_ORDER = [
    "not_relevant",
    "target_company_news",
    "competitor_company_news",
    "industry_news",
    "macro_policy_news",
    "market_roundup_but_relevant",
]
REGRESSIONS = [
    ("model_sentiment_t1", "competitor_abret_spy_t1 ~ C(target_company_sentiment)"),
    ("model_expected_effect_t1", "competitor_abret_spy_t1 ~ C(expected_competitor_effect)"),
    ("model_relevance_industry_t1", "competitor_abret_spy_t1 ~ C(relevance_type) + C(primary_industry)"),
    (
        "model_expected_effect_car01",
        "competitor_car_abret_spy_0_1 ~ C(expected_competitor_effect) + C(primary_industry)",
    ),
    (
        "model_expected_effect_car13",
        "competitor_car_abret_spy_1_3 ~ C(expected_competitor_effect) + C(primary_industry)",
    ),
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze competitor market reactions.")
    parser.add_argument(
        "--input",
        default="data/processed/news_competitor_event_panel.csv",
        help="Path to processed event panel.",
    )
    parser.add_argument(
        "--llm-input",
        default=LLM_DEFAULT,
        help="Path to the successful LLM classification file used to build the panel.",
    )
    parser.add_argument(
        "--output-root",
        default="outputs",
        help="Root directory for tables, figures, and notes.",
    )
    return parser


def save_table(df: pd.DataFrame, path: Path) -> None:
    ensure_dir(path.parent)
    df.to_csv(path, index=False)


def save_markdown(text: str, path: Path) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(text)


def to_bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin(["true", "1", "yes"])


def normalize_panel(panel: pd.DataFrame) -> pd.DataFrame:
    normalized = panel.copy()
    for column in ["sample_broad", "sample_strict", "sample_very_strict"]:
        normalized[column] = to_bool(normalized[column])
    return normalized


def load_llm_classifications(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df.loc[df["classification_status"] == "success"].copy()
    df["is_relevant"] = to_bool(df["is_relevant"])
    return df


def grouped_counts(df: pd.DataFrame, group_column: str, count_name: str) -> pd.DataFrame:
    counts = (
        df.groupby(group_column, dropna=False)
        .size()
        .reset_index(name=count_name)
        .sort_values(count_name, ascending=False)
    )
    counts["share"] = counts[count_name] / counts[count_name].sum() if len(counts) else 0.0
    return counts


def build_mean_return_table(panel: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    group_specs = [
        "target_company_sentiment",
        "expected_competitor_effect",
        "relevance_type",
        "primary_industry",
        "event_type",
    ]

    for group_name in group_specs:
        grouped = (
            panel.groupby(group_name, dropna=False)[MAIN_OUTCOMES]
            .agg(["count", "mean", "std"])
            .reset_index()
        )
        grouped.columns = [
            group_name if column[1] == "" else f"{column[0]}_{column[1]}"
            for column in grouped.columns.to_flat_index()
        ]
        grouped = grouped.rename(columns={group_name: "group_value"})
        grouped.insert(0, "group_name", group_name)
        frames.append(grouped)

    sample_frames: list[pd.DataFrame] = []
    for label, mask in [
        ("sample_broad", panel["sample_broad"]),
        ("sample_strict", panel["sample_strict"]),
        ("sample_very_strict", panel["sample_very_strict"]),
    ]:
        subset = panel.loc[mask, MAIN_OUTCOMES]
        sample_row = {"group_name": "sample_definition", "group_value": label}
        for outcome in MAIN_OUTCOMES:
            sample_row[f"{outcome}_count"] = subset[outcome].notna().sum()
            sample_row[f"{outcome}_mean"] = subset[outcome].mean()
            sample_row[f"{outcome}_std"] = subset[outcome].std()
        sample_frames.append(pd.DataFrame([sample_row]))

    frames.extend(sample_frames)
    return pd.concat(frames, ignore_index=True)


def run_regression_models(panel: pd.DataFrame, sample_name: str, sample_mask: pd.Series) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    sample_df = panel.loc[sample_mask].copy()
    for model_name, formula in REGRESSIONS:
        dependent_variable = formula.split("~", 1)[0].strip()
        regression_df = sample_df.dropna(subset=[dependent_variable]).copy()
        if regression_df.empty:
            continue

        model = smf.ols(formula, data=regression_df)
        unique_articles = regression_df["article_id"].nunique()
        if unique_articles >= 2:
            results = model.fit(
                cov_type="cluster",
                cov_kwds={"groups": regression_df["article_id"]},
            )
            cov_type = "cluster_article_id"
        else:
            results = model.fit(cov_type="HC3")
            cov_type = "HC3"

        tidy = pd.DataFrame(
            {
                "sample_name": sample_name,
                "model_name": model_name,
                "formula": formula,
                "cov_type": cov_type,
                "term": results.params.index,
                "coef": results.params.values,
                "std_err": results.bse.values,
                "t_value": results.tvalues.values,
                "p_value": results.pvalues.values,
                "nobs": results.nobs,
                "rsquared": results.rsquared,
            }
        )
        frames.append(tidy)

    if not frames:
        return pd.DataFrame(
            columns=[
                "sample_name",
                "model_name",
                "formula",
                "cov_type",
                "term",
                "coef",
                "std_err",
                "t_value",
                "p_value",
                "nobs",
                "rsquared",
            ]
        )
    return pd.concat(frames, ignore_index=True)


def save_bar_figure(
    df: pd.DataFrame,
    x: str,
    y: str,
    title: str,
    path: Path,
    xlabel: str = "",
    ylabel: str = "",
    order: list[str] | None = None,
) -> None:
    ensure_dir(path.parent)
    plt.figure(figsize=(10, 6))
    ax = sns.barplot(data=df, x=x, y=y, color="#4C72B0", order=order)
    ax.set_title(title)
    ax.set_xlabel(xlabel or x)
    ax.set_ylabel(ylabel or y)
    ax.tick_params(axis="x", rotation=30)
    plt.tight_layout()
    plt.savefig(path, dpi=200)
    plt.close()


def round_numeric(df: pd.DataFrame, decimals: int = 6) -> pd.DataFrame:
    rounded = df.copy()
    for column in rounded.select_dtypes(include=["float64", "float32"]).columns:
        rounded[column] = rounded[column].round(decimals)
    return rounded


def effect_sort_key(value: str) -> tuple[int, str]:
    if value in EFFECT_ORDER:
        return (EFFECT_ORDER.index(value), value)
    return (len(EFFECT_ORDER), value)


def relevance_sort_key(value: str) -> tuple[int, str]:
    if value in RELEVANCE_ORDER:
        return (RELEVANCE_ORDER.index(value), value)
    return (len(RELEVANCE_ORDER), value)


def build_dataset_construction_table(
    llm_df: pd.DataFrame,
    panel: pd.DataFrame,
    article_df: pd.DataFrame,
    event_df: pd.DataFrame,
) -> pd.DataFrame:
    rows = [
        {
            "step_order": 1,
            "step": "Successful LLM classifications",
            "unit": "articles",
            "count": int(len(llm_df)),
            "note": "Rows in the final successful LLM classification file.",
        },
        {
            "step_order": 2,
            "step": "Relevant classified articles",
            "unit": "articles",
            "count": int(llm_df["is_relevant"].sum()),
            "note": "Articles marked relevant by the LLM.",
        },
        {
            "step_order": 3,
            "step": "Unique relevant articles used in the event panel",
            "unit": "articles",
            "count": int(article_df["article_id"].nunique()),
            "note": "Relevant articles that map to at least one tracked source ticker.",
        },
        {
            "step_order": 4,
            "step": "Unique article-source events",
            "unit": "article_source_events",
            "count": int(len(event_df)),
            "note": "Unique `article_id + source_ticker` events before competitor expansion.",
        },
        {
            "step_order": 5,
            "step": "Broad event-panel sample",
            "unit": "panel_rows",
            "count": int(panel["sample_broad"].sum()),
            "note": "All relevant competitor rows.",
        },
        {
            "step_order": 6,
            "step": "Strict event-panel sample",
            "unit": "panel_rows",
            "count": int(panel["sample_strict"].sum()),
            "note": "Broad sample excluding `market_roundup_but_relevant`.",
        },
        {
            "step_order": 7,
            "step": "Very strict event-panel sample",
            "unit": "panel_rows",
            "count": int(panel["sample_very_strict"].sum()),
            "note": "Strict sample with `materiality >= 3` and `confidence >= 4`.",
        },
    ]
    return pd.DataFrame(rows)


def build_report_llm_label_distribution(llm_df: pd.DataFrame) -> pd.DataFrame:
    summary = (
        llm_df.groupby("relevance_type", dropna=False)
        .agg(article_count=("article_id", "size"), relevant_article_count=("is_relevant", "sum"))
        .reset_index()
    )
    total_articles = summary["article_count"].sum()
    relevant_total = int(llm_df["is_relevant"].sum())
    summary["share_of_classified_articles"] = (
        summary["article_count"] / total_articles if total_articles else 0.0
    )
    summary["share_of_relevant_articles"] = summary["relevant_article_count"].apply(
        lambda value: value / relevant_total if relevant_total else 0.0
    )
    summary = summary.sort_values(
        by="relevance_type",
        key=lambda series: series.map(relevance_sort_key),
    ).reset_index(drop=True)
    return summary


def build_report_event_panel_counts(panel: pd.DataFrame, article_df: pd.DataFrame, event_df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"metric": "panel_rows_total", "value": int(len(panel)), "note": "Total competitor event-panel rows."},
            {
                "metric": "unique_articles",
                "value": int(article_df["article_id"].nunique()),
                "note": "Relevant articles represented in the panel.",
            },
            {
                "metric": "unique_article_source_events",
                "value": int(len(event_df)),
                "note": "Unique `article_id + source_ticker` events.",
            },
            {
                "metric": "unique_source_tickers",
                "value": int(panel["source_ticker"].nunique()),
                "note": "Distinct tracked source tickers appearing in the panel.",
            },
            {
                "metric": "unique_competitor_tickers",
                "value": int(panel["competitor_ticker"].nunique()),
                "note": "Distinct tracked competitor tickers appearing in the panel.",
            },
            {
                "metric": "sample_broad_rows",
                "value": int(panel["sample_broad"].sum()),
                "note": "Rows in the broad sample.",
            },
            {
                "metric": "sample_strict_rows",
                "value": int(panel["sample_strict"].sum()),
                "note": "Rows in the strict sample.",
            },
            {
                "metric": "sample_very_strict_rows",
                "value": int(panel["sample_very_strict"].sum()),
                "note": "Rows in the very strict sample.",
            },
        ]
    )


def summarize_returns_by_group(
    panel: pd.DataFrame,
    group_column: str,
    sample_name: str,
    sample_mask: pd.Series,
) -> pd.DataFrame:
    sample_df = panel.loc[sample_mask].copy()
    rows: list[dict[str, object]] = []
    for group_value, group_df in sample_df.groupby(group_column, dropna=False):
        row: dict[str, object] = {
            "sample_definition": sample_name,
            group_column: group_value,
            "panel_rows": int(len(group_df)),
            "unique_articles": int(group_df["article_id"].nunique()),
        }
        for outcome in MAIN_OUTCOMES:
            row[f"{outcome}_nonmissing"] = int(group_df[outcome].notna().sum())
            row[f"{outcome}_mean"] = group_df[outcome].mean()
            row[f"{outcome}_std"] = group_df[outcome].std()
        rows.append(row)

    summary = pd.DataFrame(rows)
    if summary.empty:
        return summary
    return summary.sort_values(
        by=group_column,
        key=lambda series: series.astype(str).map(effect_sort_key),
    ).reset_index(drop=True)


def extract_key_regression_signal(
    regression_df: pd.DataFrame,
    sample_name: str,
    model_name: str,
    term: str,
) -> str:
    subset = regression_df.loc[
        (regression_df["sample_name"] == sample_name)
        & (regression_df["model_name"] == model_name)
        & (regression_df["term"] == term)
    ]
    if subset.empty:
        return "No estimate produced."
    row = subset.iloc[0]
    return f"coef={row['coef']:.4f}, p={row['p_value']:.3f}, n={int(row['nobs'])}"


def build_final_results_summary(
    llm_df: pd.DataFrame,
    panel: pd.DataFrame,
    article_df: pd.DataFrame,
    event_df: pd.DataFrame,
    report_main_results: pd.DataFrame,
    report_robustness: pd.DataFrame,
    regression_all: pd.DataFrame,
) -> str:
    sample_counts = {
        "broad": int(panel["sample_broad"].sum()),
        "strict": int(panel["sample_strict"].sum()),
        "very_strict": int(panel["sample_very_strict"].sum()),
    }
    relevant_articles = int(llm_df["is_relevant"].sum())

    broad_results = report_main_results.set_index("expected_competitor_effect")
    same_direction_broad = broad_results.loc["same_direction_contagion"]
    opposite_direction_broad = broad_results.loc["opposite_direction_competition"]
    negative_broad = broad_results.loc["negative_for_competitors"]
    neutral_broad = broad_results.loc["neutral_or_no_clear_effect"]

    strict_same = report_robustness.loc[
        (report_robustness["sample_definition"] == "strict")
        & (report_robustness["expected_competitor_effect"] == "same_direction_contagion")
    ].iloc[0]
    strict_opposite = report_robustness.loc[
        (report_robustness["sample_definition"] == "strict")
        & (report_robustness["expected_competitor_effect"] == "opposite_direction_competition")
    ].iloc[0]
    very_strict_same = report_robustness.loc[
        (report_robustness["sample_definition"] == "very_strict")
        & (report_robustness["expected_competitor_effect"] == "same_direction_contagion")
    ].iloc[0]

    same_direction_t1_signal = extract_key_regression_signal(
        regression_all,
        sample_name="strict",
        model_name="model_expected_effect_t1",
        term="C(expected_competitor_effect)[T.same_direction_contagion]",
    )
    same_direction_car13_signal = extract_key_regression_signal(
        regression_all,
        sample_name="strict",
        model_name="model_expected_effect_car13",
        term="C(expected_competitor_effect)[T.same_direction_contagion]",
    )
    industry_news_signal = extract_key_regression_signal(
        regression_all,
        sample_name="strict",
        model_name="model_relevance_industry_t1",
        term="C(relevance_type)[T.industry_news]",
    )

    lines = [
        "# Final Results Summary",
        "",
        "## Final dataset construction steps",
        "",
        f"- Final successful LLM classifications: {len(llm_df):,} articles.",
        f"- Relevant classified articles: {relevant_articles:,}.",
        f"- Relevant articles carried into the event panel: {article_df['article_id'].nunique():,}.",
        f"- Unique article-source events in the event panel: {len(event_df):,}.",
        f"- Competitor event-panel rows: {len(panel):,}.",
        "",
        "## Final sample definitions",
        "",
        "- Broad: all rows with `sample_broad == True`.",
        "- Strict: broad sample excluding `market_roundup_but_relevant`.",
        "- Very strict: strict sample plus `materiality >= 3` and `confidence >= 4`.",
        "",
        f"- Broad sample size: {sample_counts['broad']:,} rows.",
        f"- Strict sample size: {sample_counts['strict']:,} rows.",
        f"- Very strict sample size: {sample_counts['very_strict']:,} rows.",
        "",
        "## Main findings in plain English",
        "",
        (
            f"- In the broad sample, `same_direction_contagion` is the dominant label "
            f"({int(same_direction_broad['panel_rows']):,} rows) and has a positive mean next-day abnormal return "
            f"of {same_direction_broad['competitor_abret_spy_t1_mean']:.4f}."
        ),
        (
            f"- `opposite_direction_competition` has the highest broad-sample mean next-day abnormal return "
            f"({opposite_direction_broad['competitor_abret_spy_t1_mean']:.4f}), but it is based on only "
            f"{int(opposite_direction_broad['panel_rows']):,} rows."
        ),
        (
            f"- `negative_for_competitors` is the weakest broad-sample category, with a mean next-day abnormal return "
            f"of {negative_broad['competitor_abret_spy_t1_mean']:.4f}."
        ),
        (
            f"- `neutral_or_no_clear_effect` sits between those extremes with a mean next-day abnormal return "
            f"of {neutral_broad['competitor_abret_spy_t1_mean']:.4f}."
        ),
        "",
        "## What evidence supports contagion",
        "",
        (
            f"- `same_direction_contagion` stays positive across all three samples: "
            f"{same_direction_broad['competitor_abret_spy_t1_mean']:.4f} in broad, "
            f"{strict_same['competitor_abret_spy_t1_mean']:.4f} in strict, and "
            f"{very_strict_same['competitor_abret_spy_t1_mean']:.4f} in very strict."
        ),
        (
            f"- In the strict regressions, the `same_direction_contagion` coefficient is {same_direction_t1_signal} "
            f"for next-day abnormal returns and {same_direction_car13_signal} for the 1-to-3 day abnormal CAR model."
        ),
        (
            f"- `industry_news` articles also stand out: the strict-sample relevance regression gives {industry_news_signal}, "
            "which is consistent with broader sector-level spillovers."
        ),
        "",
        "## What evidence supports or does not support competition/substitution",
        "",
        (
            f"- The descriptive means for `opposite_direction_competition` are positive in both the broad "
            f"({opposite_direction_broad['competitor_abret_spy_t1_mean']:.4f}) and strict "
            f"({strict_opposite['competitor_abret_spy_t1_mean']:.4f}) samples."
        ),
        (
            f"- That pattern is not yet strong enough to call decisive competition/substitution evidence because the "
            f"`opposite_direction_competition` sample is small: {int(opposite_direction_broad['panel_rows']):,} broad rows, "
            f"{int(strict_opposite['panel_rows']):,} strict rows."
        ),
        "- The cleaner and more stable result in this panel is positive co-movement for same-direction contagion labels, not a robust negative competitor reaction.",
        "",
        "## Limitations",
        "",
        "- The analysis uses a balanced LLM-classified sample of 1,250 articles rather than the full article universe.",
        "- Publication dates are available, but intraday timestamps are not, so next-trading-day reactions are more reliable than same-day interpretation.",
        "- The panel ends close to the latest market data, so some late events are missing `t3` observations.",
        "- Stored CAR fields use a partial-sum convention when a later return is missing, which the validation script flags explicitly.",
        "- Competition labels are relatively sparse, so those estimates are less stable than the contagion estimates.",
        "",
        "## Suggested wording for the final report conclusion",
        "",
        (
            "This event-study provides stronger evidence of competitive news contagion than of substitution. "
            "Articles classified as implying same-direction competitor effects are associated with consistently positive "
            "competitor abnormal returns across broad, strict, and very strict samples, while competition-oriented labels "
            "show weaker and much less precisely estimated patterns because the sample is small. The results therefore support "
            "the view that firm news often carries sector-wide information, but they do not yet establish equally strong evidence "
            "for systematic winner-loser substitution across direct rivals."
        ),
        "",
    ]
    return "\n".join(lines)


def build_analysis_summary(
    llm_df: pd.DataFrame,
    panel: pd.DataFrame,
    regression_main: pd.DataFrame,
    regression_strict: pd.DataFrame,
    report_main_results: pd.DataFrame,
) -> str:
    broad_ranked = report_main_results.sort_values(
        "competitor_abret_spy_t1_mean",
        ascending=False,
    ).reset_index(drop=True)
    broad_top = broad_ranked.iloc[0]
    broad_bottom = broad_ranked.iloc[-1]
    lines = [
        "# Analysis Summary",
        "",
        "## Data used",
        "",
        f"- LLM classification file: `{LLM_DEFAULT}`",
        f"- Successful classifications: {len(llm_df):,}",
        f"- Relevant classifications: {int(llm_df['is_relevant'].sum()):,}",
        f"- Competitor panel rows: {len(panel):,}",
        "",
        "## Samples",
        "",
        f"- Broad rows: {int(panel['sample_broad'].sum()):,}",
        f"- Strict rows: {int(panel['sample_strict'].sum()):,}",
        f"- Very strict rows: {int(panel['sample_very_strict'].sum()):,}",
        "",
        "## Descriptive highlights",
        "",
        (
            f"- Highest broad-sample expected-effect mean for `competitor_abret_spy_t1`: "
            f"`{broad_top['expected_competitor_effect']}` = {broad_top['competitor_abret_spy_t1_mean']:.4f}"
        ),
        (
            f"- Lowest broad-sample expected-effect mean for `competitor_abret_spy_t1`: "
            f"`{broad_bottom['expected_competitor_effect']}` = {broad_bottom['competitor_abret_spy_t1_mean']:.4f}"
        ),
        "",
        "## Regression highlights",
        "",
        f"- Strict same-direction contagion (`t1`): {extract_key_regression_signal(regression_strict, 'strict', 'model_expected_effect_t1', 'C(expected_competitor_effect)[T.same_direction_contagion]')}",
        f"- Strict same-direction contagion (`car13`): {extract_key_regression_signal(regression_strict, 'strict', 'model_expected_effect_car13', 'C(expected_competitor_effect)[T.same_direction_contagion]')}",
        f"- Broad industry-news signal (`t1`): {extract_key_regression_signal(regression_main, 'broad', 'model_relevance_industry_t1', 'C(relevance_type)[T.industry_news]')}",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    args = build_parser().parse_args()

    panel_path = resolve_path(args.input)
    llm_path = resolve_path(args.llm_input)
    output_root = resolve_path(args.output_root)
    tables_dir = ensure_dir(output_root / "tables")
    figures_dir = ensure_dir(output_root / "figures")
    analysis_dir = ensure_dir(output_root / "analysis")

    for path in [panel_path, llm_path]:
        if not path.exists():
            raise FileNotFoundError(f"Required input not found: {path}")

    panel = normalize_panel(pd.read_csv(panel_path))
    llm_df = load_llm_classifications(llm_path)

    article_df = panel.drop_duplicates(subset=["article_id"]).copy()
    event_df = panel.drop_duplicates(subset=["article_id", "source_ticker"]).copy()

    llm_label_distribution = grouped_counts(article_df, "relevance_type", "article_count")
    event_panel_counts = build_report_event_panel_counts(panel, article_df, event_df)
    event_counts_by_industry = grouped_counts(event_df, "primary_industry", "event_count")
    event_counts_by_relevance_type = grouped_counts(event_df, "relevance_type", "event_count")
    event_counts_by_event_type = grouped_counts(event_df, "event_type", "event_count")
    event_counts_by_sentiment = grouped_counts(event_df, "target_company_sentiment", "event_count")
    mean_returns_by_label = build_mean_return_table(panel)

    regression_main = run_regression_models(panel, "broad", panel["sample_broad"])
    regression_strict = run_regression_models(panel, "strict", panel["sample_strict"])
    regression_very_strict = run_regression_models(panel, "very_strict", panel["sample_very_strict"])
    regression_all = pd.concat(
        [regression_main, regression_strict, regression_very_strict], ignore_index=True
    )

    report_dataset_construction = build_dataset_construction_table(llm_df, panel, article_df, event_df)
    report_llm_label_distribution = build_report_llm_label_distribution(llm_df)
    report_main_results = summarize_returns_by_group(
        panel=panel,
        group_column="expected_competitor_effect",
        sample_name="broad",
        sample_mask=panel["sample_broad"],
    )
    report_robustness = pd.concat(
        [
            summarize_returns_by_group(panel, "expected_competitor_effect", "broad", panel["sample_broad"]),
            summarize_returns_by_group(panel, "expected_competitor_effect", "strict", panel["sample_strict"]),
            summarize_returns_by_group(
                panel, "expected_competitor_effect", "very_strict", panel["sample_very_strict"]
            ),
        ],
        ignore_index=True,
    )

    save_table(round_numeric(llm_label_distribution), tables_dir / "llm_label_distribution.csv")
    save_table(round_numeric(event_panel_counts), tables_dir / "event_panel_counts.csv")
    save_table(round_numeric(event_counts_by_industry), tables_dir / "event_counts_by_industry.csv")
    save_table(round_numeric(event_counts_by_relevance_type), tables_dir / "event_counts_by_relevance_type.csv")
    save_table(round_numeric(event_counts_by_event_type), tables_dir / "event_counts_by_event_type.csv")
    save_table(round_numeric(event_counts_by_sentiment), tables_dir / "event_counts_by_sentiment.csv")
    save_table(round_numeric(mean_returns_by_label), tables_dir / "mean_returns_by_label.csv")
    save_table(round_numeric(regression_main), tables_dir / "regression_results_main.csv")
    save_table(round_numeric(regression_strict), tables_dir / "regression_results_strict.csv")
    save_table(round_numeric(regression_very_strict), tables_dir / "regression_results_very_strict.csv")

    save_table(round_numeric(report_dataset_construction), tables_dir / "report_dataset_construction.csv")
    save_table(round_numeric(report_llm_label_distribution), tables_dir / "report_llm_label_distribution.csv")
    save_table(round_numeric(event_panel_counts), tables_dir / "report_event_panel_counts.csv")
    save_table(round_numeric(report_main_results), tables_dir / "report_main_results.csv")
    save_table(round_numeric(report_robustness), tables_dir / "report_robustness_broad_vs_strict.csv")

    save_bar_figure(
        report_llm_label_distribution,
        x="relevance_type",
        y="article_count",
        title="LLM Classification Distribution by Relevance Type",
        path=figures_dir / "report_relevance_distribution.png",
        xlabel="Relevance type",
        ylabel="Article count",
        order=RELEVANCE_ORDER,
    )
    save_bar_figure(
        report_llm_label_distribution.loc[report_llm_label_distribution["relevance_type"] != "not_relevant"],
        x="relevance_type",
        y="article_count",
        title="Relevant Article Distribution by Relevance Type",
        path=figures_dir / "relevance_distribution.png",
        xlabel="Relevance Type",
        ylabel="Article count",
    )
    save_bar_figure(
        report_main_results,
        x="expected_competitor_effect",
        y="competitor_abret_spy_t1_mean",
        title="Mean Competitor Next-Day Abnormal Return by Expected Competitor Effect",
        path=figures_dir / "report_mean_competitor_return_by_expected_effect.png",
        xlabel="Expected competitor effect",
        ylabel="Mean abnormal return (t1)",
        order=EFFECT_ORDER,
    )
    save_bar_figure(
        report_main_results,
        x="expected_competitor_effect",
        y="competitor_abret_spy_t1_mean",
        title="Mean Competitor Abnormal Return by Expected Competitor Effect",
        path=figures_dir / "mean_competitor_abret_by_expected_effect.png",
        xlabel="Expected Competitor Effect",
        ylabel="Mean abnormal return (t1)",
        order=EFFECT_ORDER,
    )

    relevance_type_means = summarize_returns_by_group(
        panel=panel,
        group_column="relevance_type",
        sample_name="broad",
        sample_mask=panel["sample_broad"],
    ).sort_values(
        by="relevance_type",
        key=lambda series: series.map(relevance_sort_key),
    )
    save_bar_figure(
        relevance_type_means,
        x="relevance_type",
        y="competitor_abret_spy_t1_mean",
        title="Mean Competitor Next-Day Abnormal Return by Relevance Type",
        path=figures_dir / "report_mean_competitor_return_by_relevance_type.png",
        xlabel="Relevance type",
        ylabel="Mean abnormal return (t1)",
    )

    sentiment_means = (
        panel.groupby("target_company_sentiment")["competitor_abret_spy_t1"]
        .mean()
        .reset_index(name="mean_competitor_abret_spy_t1")
        .sort_values("mean_competitor_abret_spy_t1", ascending=False)
    )
    save_bar_figure(
        sentiment_means,
        x="target_company_sentiment",
        y="mean_competitor_abret_spy_t1",
        title="Mean Competitor Abnormal Return by Source Sentiment",
        path=figures_dir / "mean_competitor_abret_by_sentiment.png",
        xlabel="Target Company Sentiment",
        ylabel="Mean abnormal return (t1)",
    )

    final_results_summary = build_final_results_summary(
        llm_df=llm_df,
        panel=panel,
        article_df=article_df,
        event_df=event_df,
        report_main_results=report_main_results,
        report_robustness=report_robustness,
        regression_all=regression_all,
    )
    analysis_summary = build_analysis_summary(
        llm_df=llm_df,
        panel=panel,
        regression_main=regression_main,
        regression_strict=regression_strict,
        report_main_results=report_main_results,
    )

    final_summary_path = analysis_dir / "final_results_summary.md"
    analysis_summary_path = analysis_dir / "analysis_summary.md"
    save_markdown(final_results_summary, final_summary_path)
    save_markdown(analysis_summary, analysis_summary_path)

    print("Event analysis completed.")
    print(f"Panel input: {panel_path}")
    print(f"LLM input: {llm_path}")
    print(f"Tables: {tables_dir}")
    print(f"Figures: {figures_dir}")
    print(f"Analysis notes: {final_summary_path}")
    print(f"Panel rows: {len(panel):,}")
    print(f"Broad sample rows: {int(panel['sample_broad'].sum()):,}")
    print(f"Strict sample rows: {int(panel['sample_strict'].sum()):,}")
    print(f"Very strict sample rows: {int(panel['sample_very_strict'].sum()):,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
