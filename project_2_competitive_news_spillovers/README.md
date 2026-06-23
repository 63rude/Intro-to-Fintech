# Project 2: Competitive News Spillovers

Working title: `Contagion or Competition? An LLM-Based Study of How Corporate News Affects Rival Stock Prices`

This folder is a clean workspace for FinTech Group Project 2. It is intentionally separate from any example or facsimile materials. The project studies whether corporate news about one firm creates positive spillovers, negative competitive pressure, or no measurable reaction in rival firms' stocks.

## Research question

Does corporate news create a contagion effect or a competitive effect on rival firms?

The core idea is that the same news item can imply different consequences for competitors:

- Industry-wide good news may lift multiple firms.
- Firm-specific good news may hurt rivals if one company gains a unique advantage.
- Firm-specific bad news may help rivals when investors expect market-share substitution.
- Industry-wide bad news may depress the whole peer group.

## Initial hypotheses

- `H1`: Industry-wide positive news about one firm is associated with positive abnormal returns for competitors.
- `H2`: Firm-specific positive news about one firm is associated with negative abnormal returns for competitors.
- `H3`: Firm-specific negative news about one firm can create positive abnormal returns for competitors when the news suggests market-share substitution.
- `H4`: Industry-wide negative news about one firm is associated with negative abnormal returns for competitors.

## Why LLMs are useful here

Simple sentiment is not enough for this question. The LLM must classify the economic meaning of the news for rival firms, including:

- whether the news is firm-specific or industry-wide;
- whether the likely effect on competitors is positive, negative, neutral, or unclear;
- how material and uncertain the event appears;
- a short economic explanation that can be audited later.

## Planned data inputs

Text data candidates:

- Alpha Vantage News and Sentiment API
- Finnhub company news API
- Other low-cost or free news sources only if needed

Market data candidates:

- `yfinance` daily prices and volume
- Market benchmark ETF data for abnormal return construction

Minimum feasibility requirements:

- News text or summary, publication date, and target ticker
- Matching daily price and volume data for target firms and competitors
- Enough overlap to construct next-day and short-window competitor reactions

## Planned outputs

- A labeled news dataset with LLM-generated fields
- An event panel linking focal-firm news to competitor market reactions
- Descriptive tables and figures
- A short report summary and presentation-ready results

## Workflow

1. Confirm data feasibility for news coverage and price overlap.
2. Build a small rival-firm universe by industry.
3. Collect a pilot sample of corporate news.
4. Draft and test the LLM classification prompt.
5. Build an event-level panel with competitor outcomes.
6. Run basic market reaction analysis.
7. Document methods, limits, and interpretation.

## Folder guide

- `project_plan.md`: step-by-step execution plan
- `config/competitor_groups.yaml`: initial firm universe by industry
- `prompts/news_spillover_classification_prompt.md`: spillover-focused LLM labeling prompt
- `scripts/`: data collection, sampling, classification, and analysis scripts
- `notebooks/`: staged notebooks for feasibility, labeling tests, and event-study work
- `report/`: outline and report drafting space

## LLM Pilot Workflow

The LLM workflow is designed to stay cost-safe and resumable:

- classify unique articles only, not ticker duplicates;
- stratify first so pilot samples cover different news types;
- classify balanced samples before any larger run;
- append results incrementally so reruns skip completed `article_id` values.

### Required LLM environment variables

Add these to the project `.env` file:

```text
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-5.4-mini
```

Optional cost-estimate variables for the classifier:

```text
OPENAI_INPUT_COST_PER_1M_USD=
OPENAI_OUTPUT_COST_PER_1M_USD=
```

### Build strata and pilot sample

```bash
python scripts/build_llm_strata.py --mode hybrid --min-stratum-size 50
python scripts/build_llm_sample.py --per-stratum 20 --max-total-rows 300 --seed 42
```

This creates:

- `data/interim/news_articles_with_strata.csv`
- `outputs/tables/llm_strata_summary.csv`
- `outputs/samples/llm_strata_sample_200.csv`
- `data/processed/llm_input/llm_input_sample_n20_per_stratum_max300.csv`

Notes:

- `build_llm_strata.py` supports `--mode heuristic` and `--mode hybrid`.
- The number of final strata is data-driven rather than fixed.
- Small combined strata are collapsed with `--min-stratum-size`.
- `build_llm_sample.py` samples from every available final stratum and can cap the total with `--max-total-rows`.

### Run the sample classifier

```bash
python scripts/classify_news_with_openai.py --input data/processed/llm_input/llm_input_sample_n20_per_stratum_max300.csv --output data/processed/llm_output/llm_classifications_sample_n20_per_stratum.csv --concurrency 12
```

The classifier also writes raw API responses to:

- `data/processed/llm_output/raw_responses_sample_n20_per_stratum.jsonl`

Useful options:

- `--limit 3` for a smoke test
- `--concurrency 12` or higher to use parallel requests instead of serial classification
- `--model ...` to override `OPENAI_MODEL`
- `--structured-output auto|on|off` if the chosen model handles JSON schema differently

### Inspect the classified sample

```bash
python scripts/inspect_llm_classifications.py --input data/processed/llm_output/llm_classifications_sample_n20_per_stratum.csv
```

This creates:

- `outputs/tables/llm_classification_summary.csv`
- `outputs/samples/llm_relevant_sample_100.csv`
- `outputs/samples/llm_not_relevant_sample_100.csv`
- `outputs/samples/llm_low_confidence_sample_100.csv`

## Event Study Workflow

The current event-study stage uses the completed classified sample:

- `data/processed/llm_output/llm_classifications_sample_n50_per_stratum_max1500_final.csv`

This stage:

- downloads daily prices for all project tickers plus `SPY` and `QQQ`;
- builds daily simple returns, log returns, and simple abnormal returns versus `SPY` and `QQQ`;
- links relevant classified news to source tickers and same-group competitors;
- maps news dates to the next available trading day;
- constructs competitor and source return windows;
- exports descriptive tables, figures, regressions, and a written analysis summary.

### Price and event-study commands

```bash
python scripts/fetch_prices.py
python scripts/build_daily_returns.py
python scripts/build_event_panel.py
python scripts/run_event_analysis.py
```

### Main generated files

- Raw prices:
  - `data/raw/prices/yfinance_daily_prices.csv`
- Daily returns:
  - `data/interim/daily_returns.csv`
- Event panel:
  - `data/processed/news_competitor_event_panel.csv`
- Tables:
  - `outputs/tables/llm_label_distribution.csv`
  - `outputs/tables/event_panel_counts.csv`
  - `outputs/tables/event_counts_by_industry.csv`
  - `outputs/tables/event_counts_by_relevance_type.csv`
  - `outputs/tables/event_counts_by_event_type.csv`
  - `outputs/tables/event_counts_by_sentiment.csv`
  - `outputs/tables/mean_returns_by_label.csv`
  - `outputs/tables/regression_results_main.csv`
  - `outputs/tables/regression_results_strict.csv`
- Figures:
  - `outputs/figures/relevance_distribution.png`
  - `outputs/figures/event_counts_by_industry.png`
  - `outputs/figures/mean_competitor_abret_by_expected_effect.png`
  - `outputs/figures/mean_competitor_abret_by_sentiment.png`
- Notes:
  - `outputs/analysis/analysis_summary.md`

### Event panel definitions

- One panel row is `article_id x source_ticker x competitor_ticker`.
- `sample_broad` keeps all relevant classified events.
- `sample_strict` removes `market_roundup_but_relevant`.
- `sample_very_strict` further requires `materiality >= 3` and `confidence >= 4`.
- `competitor_abret_spy_t1` is the safest primary return outcome because exact publication time is unavailable.

## News Data Collection

This project currently supports two free/API-accessible news sources:

- Finnhub company news
- Alpha Vantage News & Sentiment

### Required API keys

Create a project-level `.env` file inside `project_2_competitive_news_spillovers/` or export the variables in your shell:

```text
FINNHUB_API_KEY=your_key_here
ALPHAVANTAGE_API_KEY=your_key_here
```

The scripts also accept the legacy alias `ALPHA_VANTAGE_API_KEY`, but `ALPHAVANTAGE_API_KEY` is the preferred variable name.

### Setup

From the project folder:

```bash
cd project_2_competitive_news_spillovers
```

The downloader reads tickers from `config/competitor_groups.yaml` unless you override them with `--tickers`.

### Small test commands

```bash
python scripts/fetch_news.py --source finnhub --tickers TSLA,NVDA,AAPL --start 2024-01-01 --end 2024-01-31 --sleep 2
python scripts/normalize_news.py --input data/raw/news --output data/interim/news_normalized.csv
```

### Full download commands

```bash
python scripts/fetch_news.py --source all --start 2023-01-01 --end 2025-12-31 --sleep 12
python scripts/normalize_news.py --input data/raw/news --output data/interim/news_normalized.csv
```

### Where files are saved

- Raw JSONL downloads:
  - `data/raw/news/finnhub_news_YYYY-MM-DD_YYYY-MM-DD.jsonl`
  - `data/raw/news/alphavantage_news_YYYY-MM-DD_YYYY-MM-DD.jsonl`
- Download checkpoint:
  - `data/raw/news/download_checkpoint.json`
- Normalized CSV:
  - `data/interim/news_normalized.csv`
- Logs:
  - `outputs/logs/fetch_news_YYYYMMDD_HHMMSS.log`
  - `outputs/logs/normalize_news_YYYYMMDD_HHMMSS.log`

### Operational notes

- The downloader is resumable. If a chunk has already been completed for the same source, ticker, and requested run window, it is skipped on rerun.
- Use `--force` to rebuild a source/date-range output from scratch.
- The script uses internal date chunks so long runs can be resumed safely and to reduce the risk of losing progress on failure.
- Alpha Vantage free usage is limited and may require multiple runs or smaller date windows.
- Finnhub company news coverage is focused on North American companies, and free-tier historical coverage may be limited.
- Raw files preserve the original API response item so later transformations remain auditable.

## Guardrails

- Do not reuse another group's code, dataset, or narrow research design.
- Use example materials only to understand the expected academic style and deliverables.
- Keep this project's topic distinct from same-stock turnover studies based on broker report titles.
- Prioritize transparent prompt documentation and reproducible event construction.
