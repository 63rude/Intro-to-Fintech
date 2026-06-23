# Analysis Summary

## Data used

- LLM classification file: `data/processed/llm_output/llm_classifications_sample_n50_per_stratum_max1500_final.csv`
- Successful classifications: 1,250
- Relevant classifications: 930
- Competitor panel rows: 4,544

## Samples

- Broad rows: 4,544
- Strict rows: 2,973
- Very strict rows: 2,273

## Descriptive highlights

- Highest broad-sample expected-effect mean for `competitor_abret_spy_t1`: `opposite_direction_competition` = 0.0072
- Lowest broad-sample expected-effect mean for `competitor_abret_spy_t1`: `negative_for_competitors` = -0.0009

## Regression highlights

- Strict same-direction contagion (`t1`): coef=0.0056, p=0.051, n=2909
- Strict same-direction contagion (`car13`): coef=0.0149, p=0.012, n=2909
- Broad industry-news signal (`t1`): coef=0.0062, p=0.004, n=4433
