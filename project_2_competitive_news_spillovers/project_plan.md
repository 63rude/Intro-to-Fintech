# Project Plan

## Objective

Build a Project 2 pipeline that links corporate news text to competitor stock reactions using LLM-based event classification.

## Phase 1: Feasibility and scope

Goal: confirm that free or low-cost sources provide enough usable text and market data.

Tasks:

1. Check which news APIs provide:
   - article text or usable summaries
   - publication dates and timestamps
   - focal ticker mapping
2. Check whether `yfinance` provides complete daily prices and volume for the same firms.
3. Test overlap for a small pilot universe before scaling.
4. Decide whether to use one source or a combined source strategy.

Deliverables:

- Feasibility notebook
- Notes on coverage gaps, rate limits, and data cleaning needs

## Phase 2: Sample design

Goal: define a clean event universe and competitor mapping.

Tasks:

1. Start with a few industries that have clear peer groups.
2. Decide whether news events must mention a single focal firm only.
3. Define exclusion rules for repeated or duplicate news items.
4. Choose an initial sample window that is realistic for API limits.

Deliverables:

- Finalized competitor groups
- Initial event inclusion and exclusion rules

## Phase 3: LLM classification design

Goal: create a prompt that classifies competitor relevance, not just tone.

Tasks:

1. Finalize output fields and controlled labels.
2. Add short economic reasoning for auditability.
3. Run a small manual spot-check set to see where the prompt fails.
4. Revise the prompt for ambiguous cases such as macro news or mixed announcements.

Deliverables:

- Prompt file
- Small manually reviewed pilot labels

## Phase 4: Event panel construction

Goal: link each labeled news item to competitor market outcomes.

Tasks:

1. Match each news item to focal firm and competitor group.
2. Compute next-day and short-window returns for competitors.
3. Choose a simple abnormal return approach for the first pass.
4. Add volume and absolute return measures if time permits.

Deliverables:

- Event-level analysis panel
- Variable definitions document in code comments and notebook notes

## Phase 5: Empirical analysis

Goal: test whether LLM labels line up with competitor reactions.

Tasks:

1. Run descriptive statistics by event type and competitor effect class.
2. Compare average competitor returns across classification buckets.
3. Estimate simple regressions with controls only if sample quality is adequate.
4. Document limits around sample size, label noise, and timing.

Deliverables:

- Tables and figures
- Interpretable first-pass results

## Phase 6: Report and submission

Goal: produce the required code archive and report summary.

Tasks:

1. Write data description and preprocessing steps.
2. Document prompt, model choice, and parameter settings.
3. Present empirical findings and limitations clearly.
4. Prepare a clean submission folder with code and report files.

Deliverables:

- Final report summary
- Submission-ready code bundle

## Practical decisions

- Start small and prove feasibility before collecting a large sample.
- Prefer daily data first; intraday data is unnecessary for the first version.
- Keep the first abnormal return design simple and transparent.
- Record every manual judgment that affects event inclusion or label interpretation.

## Key risks

- Free news APIs may provide only summaries rather than full article text.
- Rate limits may force a smaller sample window.
- Multi-firm articles may be harder to classify cleanly.
- Competitor groups may need industry-specific treatment.
- LLM labels may need manual validation on a pilot subset.
