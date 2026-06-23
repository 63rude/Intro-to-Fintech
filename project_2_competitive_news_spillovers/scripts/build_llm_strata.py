"""Create flexible, data-driven strata for balanced LLM news classification pilots."""

from __future__ import annotations

import argparse
import random
import re
from collections import Counter
from typing import Any

import pandas as pd

from utils import ensure_dir, load_ticker_config, resolve_path


MODE_CHOICES = ("heuristic", "hybrid")
INDUSTRY_BUCKETS = (
    "autos_ev",
    "semiconductors_ai",
    "big_tech_cloud",
    "airlines_travel",
    "banks_finance",
    "macro_market",
    "other_unclear",
)
ARTICLE_TYPES = (
    "earnings_guidance",
    "analyst_valuation",
    "product_strategy",
    "legal_regulatory",
    "macro_policy",
    "market_roundup",
    "investment_advice_etf",
    "other_unclear",
)
TICKER_BUCKETS = ("single_ticker", "multi_ticker")
BROAD_ARTICLE_BUCKETS = (
    "firm_event",
    "analyst_or_earnings",
    "macro_policy",
    "market_roundup_or_advice",
    "other_unclear",
)
GLOBAL_FALLBACK_STRATUM = "other_unclear__other_unclear"
INDUSTRY_SIGNAL_MAP = {
    "autos_ev": "flag_autos_ev",
    "semiconductors_ai": "flag_semiconductors_ai",
    "big_tech_cloud": "flag_big_tech_cloud",
    "airlines_travel": "flag_airlines_travel",
    "banks_finance": "flag_banks_finance",
}


PATTERNS: dict[str, re.Pattern[str]] = {
    "earnings": re.compile(
        r"\b(earnings|guidance|revenue|eps|profit|profits|quarter|quarterly|sales rise|beat estimates|miss estimates)\b",
        re.IGNORECASE,
    ),
    "analyst": re.compile(
        r"\b(analyst|price target|price targets|upgraded|downgraded|rating|overweight|underweight|outperform|underperform|valuation|pt raised|pt cut)\b",
        re.IGNORECASE,
    ),
    "legal": re.compile(
        r"\b(lawsuit|court|judge|patent|regulatory|regulator|sec\b|doj\b|antitrust|investigation|appeal|settlement|fined|approval)\b",
        re.IGNORECASE,
    ),
    "macro": re.compile(
        r"\b(fed|rates|rate cuts|interest rates|inflation|tariff|tariffs|oil|crude|opec|recession|economy|economic|geopolitics|trade war|stimulus|treasury yields?)\b",
        re.IGNORECASE,
    ),
    "investment_advice": re.compile(
        r"\b(stock to buy|stocks to buy|best stocks|top stocks|buy these|undervalued|overvalued|dividend stock|dividend stocks|investment idea|should you buy|is .* a buy)\b",
        re.IGNORECASE,
    ),
    "etf_fund": re.compile(
        r"\b(etf|etfs|index fund|mutual fund|exchange-traded fund|portfolio review|fund commentary|fund manager|fund flows?)\b",
        re.IGNORECASE,
    ),
    "market_roundup": re.compile(
        r"\b(stock market|stocks rally|markets today|dow jones|s&p 500|nasdaq 100|nasdaq composite|futures|sector update|market update|wall street|market leadership)\b",
        re.IGNORECASE,
    ),
    "product_or_technology": re.compile(
        r"\b(ai|artificial intelligence|chip|chips|semiconductor|cloud|software|platform|launch|unveil|product|technology|iphone|android|data center|smart cockpit|battery|autonomous|robotaxi)\b",
        re.IGNORECASE,
    ),
    "partnership_or_contract": re.compile(
        r"\b(partnership|partnered|partners with|contract|supply agreement|collaboration|deal with|joint venture|selected by|chosen by|signed with)\b",
        re.IGNORECASE,
    ),
    "management": re.compile(
        r"\b(ceo|cfo|chair|chairman|board|director|executive|leadership|resigns|appointed|steps down|layoff|layoffs|job cuts|restructuring)\b",
        re.IGNORECASE,
    ),
    "mna_or_investment": re.compile(
        r"\b(acquisition|acquire|merger|merge|stake|investment|invests in|buyout)\b",
        re.IGNORECASE,
    ),
    "industry_language": re.compile(
        r"\b(industry|sector|peers|rivals|competitors|market share|airline demand|carriers|chip stocks|tech stocks|ev makers|automakers|bank stocks|sector-wide|sectorwide)\b",
        re.IGNORECASE,
    ),
    "autos_ev": re.compile(
        r"\b(ev|electric vehicle|electric vehicles|automaker|automakers|auto sales|vehicle deliveries|truck|pickup|hybrid|battery)\b",
        re.IGNORECASE,
    ),
    "semiconductors_ai": re.compile(
        r"\b(ai|artificial intelligence|semiconductor|semiconductors|chip|chips|gpu|gpus|data center|server demand)\b",
        re.IGNORECASE,
    ),
    "airlines_travel": re.compile(
        r"\b(airline|airlines|travel|traveler|travellers|flight|flights|passenger|passengers|airport|fare|summer travel|carrier|carriers)\b",
        re.IGNORECASE,
    ),
    "banks_finance": re.compile(
        r"\b(bank|banks|lender|lenders|deposit|deposits|loan|loans|credit card|net interest income|capital ratios?|stress test|wealth management|mortgage)\b",
        re.IGNORECASE,
    ),
    "big_tech_cloud": re.compile(
        r"\b(cloud|iphone|ios|android|search ads|ad spending|e-commerce|aws|azure)\b",
        re.IGNORECASE,
    ),
}


LEGACY_STRATUM_PRIORITY = [
    "investment_advice_etf_roundup_or_unclear",
    "macro_market_rates_tariffs_oil",
    "legal_regulatory_policy",
    "firm_specific_earnings_or_guidance",
    "firm_specific_analyst_or_valuation",
    "industry_wide_semiconductors_ai",
    "industry_wide_autos_ev",
    "industry_wide_airlines_travel",
    "industry_wide_banks_finance",
    "firm_specific_product_or_strategy",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build flexible LLM strata for news articles.")
    parser.add_argument(
        "--input",
        default="data/interim/news_unique_articles.csv",
        help="Input unique article CSV.",
    )
    parser.add_argument(
        "--config",
        default="config/competitor_groups.yaml",
        help="Ticker group configuration file.",
    )
    parser.add_argument(
        "--output",
        default="data/interim/news_articles_with_strata.csv",
        help="Output article-level CSV with strata and helper flags.",
    )
    parser.add_argument(
        "--summary-output",
        default="outputs/tables/llm_strata_summary.csv",
        help="Output CSV for strata summary tables.",
    )
    parser.add_argument(
        "--sample-output",
        default="outputs/samples/llm_strata_sample_200.csv",
        help="Balanced inspection sample output.",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=200,
        help="Inspection sample size target across final strata.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for balanced inspection sampling.",
    )
    parser.add_argument(
        "--mode",
        choices=MODE_CHOICES,
        default="hybrid",
        help="Strata construction mode. `heuristic` uses industry + article type; `hybrid` also includes ticker breadth.",
    )
    parser.add_argument(
        "--min-stratum-size",
        type=int,
        default=50,
        help="Collapse initial strata smaller than this threshold into broader fallback strata.",
    )
    parser.add_argument(
        "--max-strata",
        type=int,
        default=25,
        help="Maximum number of final strata to keep after collapsing the smallest strata into broader fallbacks.",
    )
    return parser


def clean_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def split_semicolon(value: Any) -> list[str]:
    text = clean_text(value)
    if not text:
        return []
    return [part.strip().upper() for part in text.split(";") if part.strip()]


def build_industry_map(config: dict[str, Any]) -> dict[str, str]:
    industries = config.get("industries", {})
    industry_map: dict[str, str] = {}
    for industry_name, payload in industries.items():
        if not isinstance(payload, dict):
            continue
        for ticker in payload.get("tickers", []):
            ticker_text = str(ticker).strip().upper()
            if ticker_text:
                industry_map[ticker_text] = str(industry_name)
    return industry_map


def map_industry_label(raw_name: str) -> str:
    mapping = {
        "ev_autos": "autos_ev",
        "semiconductors": "semiconductors_ai",
        "airlines": "airlines_travel",
        "banks": "banks_finance",
        "big_tech": "big_tech_cloud",
    }
    return mapping.get(raw_name, raw_name)


def collect_industry_groups(linked_tickers: str, industry_map: dict[str, str]) -> list[str]:
    groups: list[str] = []
    for ticker in split_semicolon(linked_tickers):
        group = industry_map.get(ticker)
        if group and group not in groups:
            groups.append(group)
    return groups


def match_flag(pattern_name: str, text: str) -> bool:
    return bool(PATTERNS[pattern_name].search(text))


def detect_flags(row: pd.Series, industry_map: dict[str, str]) -> dict[str, Any]:
    text = " ".join(
        part for part in [clean_text(row.get("title")), clean_text(row.get("summary"))] if part
    )
    linked_ticker_count = int(row.get("linked_ticker_count", 0) or 0)
    industry_groups = collect_industry_groups(row.get("linked_tickers", ""), industry_map)
    industry_labels = [map_industry_label(name) for name in industry_groups]

    flags: dict[str, Any] = {
        "industry_groups": ";".join(industry_groups),
        "industry_labels": ";".join(industry_labels),
        "flag_multi_ticker": linked_ticker_count >= 2,
        "flag_cross_industry_links": len(industry_groups) >= 2,
    }

    for key in PATTERNS:
        flags[f"flag_{key}"] = match_flag(key, text)

    flags["flag_company_specific_shape"] = (
        linked_ticker_count == 1
        and not flags["flag_market_roundup"]
        and not flags["flag_industry_language"]
    )
    flags["flag_industry_wide_shape"] = (
        linked_ticker_count >= 2
        or flags["flag_industry_language"]
        or flags["flag_market_roundup"]
    )
    flags["flag_has_summary"] = bool(clean_text(row.get("summary")))
    return flags


def assign_legacy_stratum(row: pd.Series, flags: dict[str, Any]) -> tuple[str, str]:
    linked_ticker_count = int(row.get("linked_ticker_count", 0) or 0)

    if (
        flags["flag_investment_advice"]
        or flags["flag_etf_fund"]
        or (flags["flag_market_roundup"] and not flags["flag_macro"])
    ):
        return (
            "investment_advice_etf_roundup_or_unclear",
            "Advice/ETF/market-roundup language dominates the article text.",
        )

    if flags["flag_macro"]:
        return (
            "macro_market_rates_tariffs_oil",
            "Macro or policy language such as rates, tariffs, oil, or inflation is present.",
        )

    if flags["flag_legal"]:
        return (
            "legal_regulatory_policy",
            "Legal, court, regulatory, or investigation language is present.",
        )

    if flags["flag_earnings"] and (
        flags["flag_company_specific_shape"] or linked_ticker_count <= 2
    ):
        return (
            "firm_specific_earnings_or_guidance",
            "Earnings or guidance language appears tied to one or two linked firms.",
        )

    if flags["flag_analyst"] and (
        flags["flag_company_specific_shape"] or linked_ticker_count <= 2
    ):
        return (
            "firm_specific_analyst_or_valuation",
            "Analyst, rating, or valuation language appears primarily firm-specific.",
        )

    labels = {label for label in str(flags.get("industry_labels", "")).split(";") if label}
    broader_context = (
        flags["flag_multi_ticker"]
        or flags["flag_cross_industry_links"]
        or flags["flag_industry_language"]
        or flags["flag_market_roundup"]
    )

    if "airlines_travel" in labels and flags["flag_industry_wide_shape"] and flags["flag_airlines_travel"]:
        return (
            "industry_wide_airlines_travel",
            "Industry-linked keywords plus ticker breadth/sector language indicate an industry-wide airline/travel article.",
        )

    if "banks_finance" in labels and flags["flag_industry_wide_shape"] and flags["flag_banks_finance"]:
        return (
            "industry_wide_banks_finance",
            "Industry-linked keywords plus ticker breadth/sector language indicate an industry-wide bank/finance article.",
        )

    if "autos_ev" in labels and flags["flag_industry_wide_shape"] and flags["flag_autos_ev"] and broader_context:
        return (
            "industry_wide_autos_ev",
            "Industry-linked keywords plus ticker breadth/sector language indicate an industry-wide autos/EV article.",
        )

    if broader_context and (flags["flag_semiconductors_ai"] or flags["flag_big_tech_cloud"]):
        return (
            "industry_wide_semiconductors_ai",
            "Industry-linked keywords plus ticker breadth/sector language indicate an industry-wide semiconductors/AI article.",
        )

    if (
        flags["flag_product_or_technology"]
        or flags["flag_partnership_or_contract"]
        or flags["flag_management"]
        or flags["flag_mna_or_investment"]
        or flags["flag_company_specific_shape"]
    ):
        return (
            "firm_specific_product_or_strategy",
            "The article looks focused on one firm's product, strategy, contract, management, or deal activity.",
        )

    return (
        "investment_advice_etf_roundup_or_unclear",
        "Fallback bucket for articles without a cleaner firm, industry, legal, or macro signal.",
    )


def assign_industry_bucket(row: pd.Series, flags: dict[str, Any]) -> tuple[str, str]:
    linked_labels = [label for label in str(flags.get("industry_labels", "")).split(";") if label]
    linked_label_set = set(linked_labels)
    signal_hits = {
        bucket for bucket, flag_name in INDUSTRY_SIGNAL_MAP.items() if flags.get(flag_name, False)
    }

    if flags["flag_macro"] and not linked_label_set and not signal_hits:
        return "macro_market", "Macro language dominates and no clearer sector signal is present."

    if len(linked_label_set) == 1:
        linked_label = next(iter(linked_label_set))
        if linked_label in signal_hits or not signal_hits or not flags["flag_multi_ticker"]:
            return linked_label, "Linked tickers map cleanly to one competitor group."

    aligned_hits = [label for label in linked_labels if label in signal_hits]
    if len(set(aligned_hits)) == 1:
        return aligned_hits[0], "Linked tickers and article keywords align to one competitor group."

    if len(signal_hits) == 1:
        signal_label = next(iter(signal_hits))
        return signal_label, "Article keywords point to one clear industry bucket."

    if flags["flag_macro"]:
        return "macro_market", "Macro language is present but sector mapping is mixed."

    if len(linked_label_set) > 1:
        return "other_unclear", "Multiple linked competitor groups appear without one dominant industry signal."

    if linked_labels:
        return linked_labels[0], "Falling back to the linked ticker industry group."

    return "other_unclear", "No stable industry bucket could be inferred from linked tickers or article text."


def assign_article_type(flags: dict[str, Any]) -> tuple[str, str]:
    if flags["flag_investment_advice"] or flags["flag_etf_fund"]:
        return "investment_advice_etf", "Investment-advice or ETF language is present."

    if flags["flag_macro"]:
        return "macro_policy", "Macro or policy language is present."

    if flags["flag_legal"]:
        return "legal_regulatory", "Legal or regulatory language is present."

    if flags["flag_earnings"]:
        return "earnings_guidance", "Earnings or guidance language is present."

    if flags["flag_analyst"]:
        return "analyst_valuation", "Analyst, rating, or valuation language is present."

    if flags["flag_market_roundup"]:
        return "market_roundup", "Market roundup or broad market language is present."

    if (
        flags["flag_product_or_technology"]
        or flags["flag_partnership_or_contract"]
        or flags["flag_management"]
        or flags["flag_mna_or_investment"]
        or flags["flag_company_specific_shape"]
    ):
        return "product_strategy", "Product, strategy, contract, management, or firm-specific execution language is present."

    return "other_unclear", "No stronger article-type pattern dominated the text."


def assign_ticker_count_bucket(row: pd.Series) -> tuple[str, str]:
    linked_ticker_count = int(row.get("linked_ticker_count", 0) or 0)
    if linked_ticker_count >= 2:
        return "multi_ticker", "Article links to multiple tracked tickers."
    return "single_ticker", "Article links to a single tracked ticker."


def assign_broad_article_bucket(article_type: str) -> tuple[str, str]:
    if article_type in {"product_strategy", "legal_regulatory"}:
        return "firm_event", "Detailed article type maps into the broad firm-event bucket."
    if article_type in {"analyst_valuation", "earnings_guidance"}:
        return "analyst_or_earnings", "Detailed article type maps into the broad analyst-or-earnings bucket."
    if article_type == "macro_policy":
        return "macro_policy", "Detailed article type stays in the macro-policy bucket."
    if article_type in {"market_roundup", "investment_advice_etf"}:
        return "market_roundup_or_advice", "Detailed article type maps into the broad market-roundup-or-advice bucket."
    return "other_unclear", "Detailed article type falls into the broad other/unclear bucket."


def build_initial_stratum(
    mode: str,
    industry_bucket: str,
    article_type: str,
    broad_article_bucket: str,
    ticker_count_bucket: str,
) -> str:
    if mode == "heuristic":
        return f"{industry_bucket}__{article_type}"
    return f"{industry_bucket}__{broad_article_bucket}"


def get_industry_fallback_stratum(industry_bucket: str) -> str:
    return f"{industry_bucket}__other_unclear"


def apply_stratum_collapsing(df: pd.DataFrame, min_stratum_size: int, max_strata: int) -> pd.DataFrame:
    enriched = df.copy()
    initial_counts = Counter(enriched["stratum_initial"])
    industry_counts = Counter(enriched["industry_bucket"])

    def stage_one(row: pd.Series) -> str:
        if initial_counts[row["stratum_initial"]] >= min_stratum_size:
            return row["stratum_initial"]
        if industry_counts[row["industry_bucket"]] >= min_stratum_size:
            return get_industry_fallback_stratum(row["industry_bucket"])
        return GLOBAL_FALLBACK_STRATUM

    enriched["stratum_stage_one"] = enriched.apply(stage_one, axis=1)
    stage_one_counts = Counter(enriched["stratum_stage_one"])

    def final_stratum(row: pd.Series) -> str:
        stage_one_value = row["stratum_stage_one"]
        if stage_one_value == GLOBAL_FALLBACK_STRATUM:
            return stage_one_value
        if stage_one_counts[stage_one_value] >= min_stratum_size:
            return stage_one_value
        return GLOBAL_FALLBACK_STRATUM

    enriched["stratum"] = enriched.apply(final_stratum, axis=1)

    if max_strata > 0:
        collapse_steps: list[str] = []
        iteration_guard = 0
        while enriched["stratum"].nunique() > max_strata and iteration_guard < len(enriched) * 2:
            iteration_guard += 1
            stratum_counts = enriched["stratum"].value_counts().sort_values()
            candidates = [stratum for stratum in stratum_counts.index if stratum != GLOBAL_FALLBACK_STRATUM]
            if not candidates:
                break

            stratum_to_collapse = candidates[0]
            if stratum_to_collapse.endswith("__other_unclear"):
                target_stratum = GLOBAL_FALLBACK_STRATUM
            else:
                industry_bucket = str(stratum_to_collapse).split("__", 1)[0]
                target_stratum = get_industry_fallback_stratum(industry_bucket)
                if target_stratum == stratum_to_collapse:
                    target_stratum = GLOBAL_FALLBACK_STRATUM

            enriched.loc[enriched["stratum"] == stratum_to_collapse, "stratum"] = target_stratum
            collapse_steps.append(f"{stratum_to_collapse} -> {target_stratum}")

        if collapse_steps:
            enriched["max_strata_collapse_steps"] = "; ".join(collapse_steps)
        else:
            enriched["max_strata_collapse_steps"] = ""
    else:
        enriched["max_strata_collapse_steps"] = ""

    def collapse_reason(row: pd.Series) -> str:
        if row["stratum"] == row["stratum_initial"]:
            return "Initial stratum met the minimum size threshold."
        if row["stratum"] == GLOBAL_FALLBACK_STRATUM:
            if row["stratum_stage_one"] == GLOBAL_FALLBACK_STRATUM:
                return "Initial stratum and its industry bucket were both too small, or later max-strata collapse pushed it into the global fallback."
            return "Initial stratum was too small and later collapsing pushed it into the global fallback."
        if row["stratum"] == row["stratum_stage_one"] and row["stratum_stage_one"] != row["stratum_initial"]:
            return "Initial stratum was too small, so it collapsed to the broader industry-level fallback."
        if row["stratum"] != row["stratum_stage_one"]:
            return "Initial stratum survived the minimum-size pass but was later collapsed to respect the max-strata limit."
        return "Initial stratum was too small, so it collapsed to the broader industry-level fallback."

    enriched["stratum_collapse_reason"] = enriched.apply(collapse_reason, axis=1)
    return enriched


def allocate_evenly(available_counts: dict[str, int], total_target: int, seed: int) -> dict[str, int]:
    if total_target <= 0:
        return {stratum: 0 for stratum in available_counts}

    ordered_strata = [stratum for stratum, count in available_counts.items() if count > 0]
    rng = random.Random(seed)
    rng.shuffle(ordered_strata)

    allocation = {stratum: 0 for stratum in available_counts}
    remaining = total_target

    while remaining > 0 and ordered_strata:
        progressed = False
        next_round: list[str] = []
        for stratum in ordered_strata:
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
        ordered_strata = next_round
    return allocation


def sample_evenly(df: pd.DataFrame, sample_size: int, seed: int) -> pd.DataFrame:
    strata = sorted(df["stratum"].dropna().unique())
    if not strata or sample_size <= 0:
        return df.iloc[0:0].copy()

    available_counts = {stratum: int((df["stratum"] == stratum).sum()) for stratum in strata}
    target_counts = allocate_evenly(available_counts, min(sample_size, len(df)), seed)

    sampled_frames: list[pd.DataFrame] = []
    for index, stratum in enumerate(strata):
        take_n = target_counts.get(stratum, 0)
        if take_n <= 0:
            continue
        subset = df.loc[df["stratum"] == stratum].sort_values(["published_date", "article_id"])
        sampled = subset.sample(n=take_n, random_state=seed + index)
        sampled_frames.append(sampled)

    if not sampled_frames:
        return df.iloc[0:0].copy()

    return (
        pd.concat(sampled_frames, ignore_index=True)
        .sort_values(["stratum", "published_date", "article_id"])
        .reset_index(drop=True)
    )


def build_summary_table(df: pd.DataFrame) -> pd.DataFrame:
    stratum_counts = (
        df.groupby("stratum", dropna=False)
        .size()
        .reset_index(name="article_count")
        .assign(
            summary_type="stratum_counts",
            publisher="",
            linked_ticker_count="",
            industry_bucket="",
            article_type="",
            ticker_count_bucket="",
        )
    )

    publisher_counts = (
        df.groupby(["stratum", "publisher"], dropna=False)
        .size()
        .reset_index(name="article_count")
        .assign(
            summary_type="publisher_counts",
            linked_ticker_count="",
            industry_bucket="",
            article_type="",
            ticker_count_bucket="",
        )
    )

    linked_ticker_counts = (
        df.groupby(["stratum", "linked_ticker_count"], dropna=False)
        .size()
        .reset_index(name="article_count")
        .assign(
            summary_type="linked_ticker_count_distribution",
            publisher="",
            industry_bucket="",
            article_type="",
            ticker_count_bucket="",
        )
    )

    component_counts = (
        df.groupby(["industry_bucket", "article_type", "ticker_count_bucket"], dropna=False)
        .size()
        .reset_index(name="article_count")
        .assign(summary_type="component_counts", stratum="", publisher="", linked_ticker_count="")
    )

    summary = pd.concat(
        [
            stratum_counts[
                [
                    "summary_type",
                    "stratum",
                    "publisher",
                    "linked_ticker_count",
                    "industry_bucket",
                    "article_type",
                    "ticker_count_bucket",
                    "article_count",
                ]
            ],
            publisher_counts[
                [
                    "summary_type",
                    "stratum",
                    "publisher",
                    "linked_ticker_count",
                    "industry_bucket",
                    "article_type",
                    "ticker_count_bucket",
                    "article_count",
                ]
            ],
            linked_ticker_counts[
                [
                    "summary_type",
                    "stratum",
                    "publisher",
                    "linked_ticker_count",
                    "industry_bucket",
                    "article_type",
                    "ticker_count_bucket",
                    "article_count",
                ]
            ],
            component_counts[
                [
                    "summary_type",
                    "stratum",
                    "publisher",
                    "linked_ticker_count",
                    "industry_bucket",
                    "article_type",
                    "ticker_count_bucket",
                    "article_count",
                ]
            ],
        ],
        ignore_index=True,
    )

    summary["share_within_group"] = summary.groupby(
        ["summary_type", "stratum", "industry_bucket", "article_type", "ticker_count_bucket"]
    )["article_count"].transform(lambda series: series / series.sum() if series.sum() else 0.0)

    return summary.sort_values(
        [
            "summary_type",
            "stratum",
            "industry_bucket",
            "article_type",
            "ticker_count_bucket",
            "article_count",
        ],
        ascending=[True, True, True, True, True, False],
    )


def main() -> int:
    args = build_parser().parse_args()

    input_path = resolve_path(args.input)
    config_path = resolve_path(args.config)
    output_path = resolve_path(args.output)
    summary_output = resolve_path(args.summary_output)
    sample_output = resolve_path(args.sample_output)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    if args.min_stratum_size <= 0:
        raise ValueError("--min-stratum-size must be positive.")
    if args.max_strata <= 0:
        raise ValueError("--max-strata must be positive.")

    df = pd.read_csv(input_path)
    required_columns = [
        "article_id",
        "published_date",
        "title",
        "summary",
        "publisher",
        "linked_ticker_count",
        "linked_tickers",
    ]
    missing = [column for column in required_columns if column not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in input: {missing}")

    config = load_ticker_config(config_path)
    industry_map = build_industry_map(config)

    flags_df = df.apply(lambda row: pd.Series(detect_flags(row, industry_map)), axis=1)
    enriched = pd.concat([df.copy(), flags_df], axis=1)

    legacy_assignments = enriched.apply(
        lambda row: pd.Series(assign_legacy_stratum(row, row.to_dict()), index=["legacy_stratum", "legacy_stratum_reason"]),
        axis=1,
    )
    enriched = pd.concat([enriched, legacy_assignments], axis=1)

    industry_assignments = enriched.apply(
        lambda row: pd.Series(assign_industry_bucket(row, row.to_dict()), index=["industry_bucket", "industry_bucket_reason"]),
        axis=1,
    )
    article_assignments = enriched.apply(
        lambda row: pd.Series(assign_article_type(row.to_dict()), index=["article_type", "article_type_reason"]),
        axis=1,
    )
    ticker_assignments = enriched.apply(
        lambda row: pd.Series(assign_ticker_count_bucket(row), index=["ticker_count_bucket", "ticker_count_bucket_reason"]),
        axis=1,
    )
    broad_article_assignments = article_assignments["article_type"].apply(
        lambda value: pd.Series(
            assign_broad_article_bucket(str(value)),
            index=["broad_article_bucket", "broad_article_bucket_reason"],
        )
    )
    enriched = pd.concat(
        [enriched, industry_assignments, article_assignments, ticker_assignments, broad_article_assignments],
        axis=1,
    )

    enriched["stratum_initial"] = enriched.apply(
        lambda row: build_initial_stratum(
            args.mode,
            row["industry_bucket"],
            row["article_type"],
            row["broad_article_bucket"],
            row["ticker_count_bucket"],
        ),
        axis=1,
    )
    enriched = apply_stratum_collapsing(enriched, args.min_stratum_size, args.max_strata)
    enriched["stratum_reason"] = (
        "mode="
        + args.mode
        + "; industry="
        + enriched["industry_bucket"]
        + "; broad_article_bucket="
        + enriched["broad_article_bucket"]
        + "; article_type="
        + enriched["article_type"]
        + "; ticker_count_bucket="
        + enriched["ticker_count_bucket"]
        + "; "
        + enriched["stratum_collapse_reason"]
    )

    helper_columns = [
        "legacy_stratum",
        "legacy_stratum_reason",
        "industry_groups",
        "industry_labels",
        "industry_bucket",
        "industry_bucket_reason",
        "article_type",
        "article_type_reason",
        "broad_article_bucket",
        "broad_article_bucket_reason",
        "ticker_count_bucket",
        "ticker_count_bucket_reason",
        "stratum_initial",
        "stratum_stage_one",
        "stratum_collapse_reason",
        "max_strata_collapse_steps",
        "flag_multi_ticker",
        "flag_cross_industry_links",
        "flag_company_specific_shape",
        "flag_industry_wide_shape",
        "flag_earnings",
        "flag_analyst",
        "flag_legal",
        "flag_macro",
        "flag_investment_advice",
        "flag_etf_fund",
        "flag_market_roundup",
        "flag_product_or_technology",
        "flag_partnership_or_contract",
        "flag_management",
        "flag_mna_or_investment",
        "flag_industry_language",
        "flag_autos_ev",
        "flag_semiconductors_ai",
        "flag_airlines_travel",
        "flag_banks_finance",
        "flag_big_tech_cloud",
        "flag_has_summary",
    ]

    ordered_columns = [
        column for column in enriched.columns if column not in {"stratum", "stratum_reason", *helper_columns}
    ] + ["stratum", "stratum_reason"] + helper_columns
    enriched = enriched[ordered_columns]

    summary = build_summary_table(enriched)
    sample_base_columns = [
        "article_id",
        "published_date",
        "publisher",
        "linked_ticker_count",
        "linked_tickers",
        "industry_bucket",
        "broad_article_bucket",
        "article_type",
        "ticker_count_bucket",
        "stratum_initial",
        "stratum",
        "stratum_reason",
        "title",
        "summary",
    ]
    sample_columns = sample_base_columns + [
        column for column in helper_columns if column not in sample_base_columns
    ]
    inspection_sample = sample_evenly(enriched[sample_columns], args.sample_size, args.seed)

    ensure_dir(output_path.parent)
    ensure_dir(summary_output.parent)
    ensure_dir(sample_output.parent)
    enriched.to_csv(output_path, index=False)
    summary.to_csv(summary_output, index=False)
    inspection_sample.to_csv(sample_output, index=False)

    stratum_counts = enriched["stratum"].value_counts().sort_values(ascending=False)

    print("LLM strata build completed.")
    print(f"Mode: {args.mode}")
    print(f"Minimum stratum size: {args.min_stratum_size}")
    print(f"Maximum final strata: {args.max_strata}")
    print(f"Input articles: {len(df):,}")
    print(f"Final stratum count: {enriched['stratum'].nunique():,}")
    print(f"Output with strata: {output_path}")
    print(f"Summary table: {summary_output}")
    print(f"Inspection sample: {sample_output}")

    print("\nArticles per final stratum:")
    print(stratum_counts.to_string())

    print("\nInitial combined strata before collapse:")
    initial_counts = enriched["stratum_initial"].value_counts().sort_values(ascending=False)
    print(initial_counts.head(30).to_string())

    print("\nLegacy broad strata preview:")
    legacy_preview = (
        enriched["legacy_stratum"].value_counts().reindex(LEGACY_STRATUM_PRIORITY, fill_value=0)
    )
    print(legacy_preview.to_string())

    print("\nTop publishers by final stratum:")
    publisher_preview = (
        enriched.groupby(["stratum", "publisher"])
        .size()
        .reset_index(name="article_count")
        .sort_values(["stratum", "article_count"], ascending=[True, False])
        .groupby("stratum")
        .head(5)
    )
    print(publisher_preview.to_string(index=False))

    print("\nLinked ticker counts by final stratum:")
    linked_preview = (
        enriched.groupby(["stratum", "linked_ticker_count"])
        .size()
        .reset_index(name="article_count")
        .sort_values(["stratum", "linked_ticker_count"])
    )
    print(linked_preview.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
