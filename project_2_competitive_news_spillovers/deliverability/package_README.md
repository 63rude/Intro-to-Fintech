Competitive News Spillovers: Reproducibility Package

Contents:
- `config/`, `scripts/`, `prompts/`, `notebooks/`
- `data/` with raw, interim, and processed pipeline files
- `outputs/` with core non-report analysis artifacts
- `requirements.txt`
- `config/example.env`

Environment:
- Python 3.11+ recommended
- Install dependencies with `python -m pip install -r requirements.txt`
- Copy `config/example.env` to `.env` and fill any API keys only if you want to rerun scraping or LLM classification

Core pipeline order:
1. `python scripts/fetch_news.py`
2. `python scripts/normalize_news.py`
3. `python scripts/basic_clean_news.py`
4. `python scripts/build_unique_articles.py`
5. `python scripts/build_llm_strata.py`
6. `python scripts/build_llm_sample.py`
7. `python scripts/classify_news_with_openai.py`
8. `python scripts/inspect_llm_classifications.py`
9. `python scripts/fetch_prices.py`
10. `python scripts/build_daily_returns.py`
11. `python scripts/build_event_panel.py`
12. `python scripts/validate_event_panel.py`
13. `python scripts/run_event_analysis.py`

Notes:
- The package already includes the downloaded news, price data, LLM outputs, and event panel, so the project can also be reproduced from intermediate stages without rerunning every API-dependent step.
- Report-writing files, logs, planning notes, and private environment values were intentionally removed from this package.
