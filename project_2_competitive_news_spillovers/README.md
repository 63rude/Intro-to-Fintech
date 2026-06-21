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
- `prompts/news_classification_prompt.md`: draft LLM labeling prompt
- `scripts/`: placeholder scripts for data collection, classification, and analysis
- `notebooks/`: staged notebooks for feasibility, labeling tests, and event-study work
- `report/`: outline and report drafting space

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
