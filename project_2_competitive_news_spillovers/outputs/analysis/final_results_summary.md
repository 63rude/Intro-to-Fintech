# Final Results Summary

## Final dataset construction steps

- Final successful LLM classifications: 1,250 articles.
- Relevant classified articles: 930.
- Relevant articles carried into the event panel: 930.
- Unique article-source events in the event panel: 1,351.
- Competitor event-panel rows: 4,544.

## Final sample definitions

- Broad: all rows with `sample_broad == True`.
- Strict: broad sample excluding `market_roundup_but_relevant`.
- Very strict: strict sample plus `materiality >= 3` and `confidence >= 4`.

- Broad sample size: 4,544 rows.
- Strict sample size: 2,973 rows.
- Very strict sample size: 2,273 rows.

## Main findings in plain English

- In the broad sample, `same_direction_contagion` is the dominant label (3,093 rows) and has a positive mean next-day abnormal return of 0.0027.
- `opposite_direction_competition` has the highest broad-sample mean next-day abnormal return (0.0072), but it is based on only 39 rows.
- `negative_for_competitors` is the weakest broad-sample category, with a mean next-day abnormal return of -0.0009.
- `neutral_or_no_clear_effect` sits between those extremes with a mean next-day abnormal return of 0.0012.

## What evidence supports contagion

- `same_direction_contagion` stays positive across all three samples: 0.0027 in broad, 0.0028 in strict, and 0.0028 in very strict.
- In the strict regressions, the `same_direction_contagion` coefficient is coef=0.0056, p=0.051, n=2909 for next-day abnormal returns and coef=0.0149, p=0.012, n=2909 for the 1-to-3 day abnormal CAR model.
- `industry_news` articles also stand out: the strict-sample relevance regression gives coef=0.0062, p=0.003, n=2909, which is consistent with broader sector-level spillovers.

## What evidence supports or does not support competition/substitution

- The descriptive means for `opposite_direction_competition` are positive in both the broad (0.0072) and strict (0.0045) samples.
- That pattern is not yet strong enough to call decisive competition/substitution evidence because the `opposite_direction_competition` sample is small: 39 broad rows, 27 strict rows.
- The cleaner and more stable result in this panel is positive co-movement for same-direction contagion labels, not a robust negative competitor reaction.

## Limitations

- The analysis uses a balanced LLM-classified sample of 1,250 articles rather than the full article universe.
- Publication dates are available, but intraday timestamps are not, so next-trading-day reactions are more reliable than same-day interpretation.
- The panel ends close to the latest market data, so some late events are missing `t3` observations.
- Stored CAR fields use a partial-sum convention when a later return is missing, which the validation script flags explicitly.
- Competition labels are relatively sparse, so those estimates are less stable than the contagion estimates.

## Suggested wording for the final report conclusion

This event-study provides stronger evidence of competitive news contagion than of substitution. Articles classified as implying same-direction competitor effects are associated with consistently positive competitor abnormal returns across broad, strict, and very strict samples, while competition-oriented labels show weaker and much less precisely estimated patterns because the sample is small. The results therefore support the view that firm news often carries sector-wide information, but they do not yet establish equally strong evidence for systematic winner-loser substitution across direct rivals.
