# Contagion or Competition? An LLM-Based Event Study of Corporate News Spillovers Across Competitor Stocks

## Abstract

This report studies whether corporate news about a public company is associated with short-run abnormal returns among direct competitors, and whether those spillovers are more consistent with industry contagion or with competitive substitution. The underlying news archive contains 55,094 raw ticker-level rows for 22 public firms across five competitor groups over 2025-06-26 to 2026-06-21. After conservative preprocessing, the cleaned ticker-level dataset contains 52,538 rows and the deduplicated article dataset contains 38,131 unique articles. A balanced stratified sample of 1,250 articles was then classified with a large language model, of which 930 were labeled relevant. Those relevant articles were merged back to source tickers and expanded into a competitor event panel with 4,544 rows.

The empirical design combines prompt-engineered LLM classification with a daily event-study framework. The model assigns structured labels for relevance, relevance type, event type, sentiment, news scope, expected competitor effect, materiality, and confidence. These labels are linked to SPY-adjusted competitor abnormal returns on the next trading day and over short cumulative windows. Results are reported for a broad sample, a strict sample that excludes relevant market roundups, and a very strict sample that also requires higher materiality and confidence.

The main findings are more consistent with short-run industry contagion than with pure competitive substitution. Industry news is positive and statistically significant in the next-day competitor abnormal-return regressions in both broad and strict samples. Same-direction contagion is also positive, with stronger evidence in the cumulative CAR(1,3) window and in the stricter sample. Competition-style labels appear in the data, but they are rare and their regression evidence is imprecise. Overall, the evidence suggests that corporate news often carries sector-level information that investors apply to rivals as well as to the focal firm. The design remains exploratory because the classified sample is structured rather than exhaustive, event timing is daily rather than intraday, and competition-oriented events are sparse.

## 1. Question Description & Theory Basis

Financial markets respond to new information because prices reflect expectations about future cash flows, risk, and competitive position. When a firm releases earnings, announces a product, faces regulation, or experiences an operational shock, investors update beliefs not only about that firm but also about nearby firms that share customers, technology, regulation, or macro exposure. This project asks whether such news spills over to direct competitors and, if so, whether the spillover is better described as contagion or competition.

That distinction matters because the same focal article can imply two different economic mechanisms. Under industry contagion, news about one firm reveals common information about the sector. Good news can raise rival valuations if it signals stronger demand, healthier pricing, faster adoption, or lower regulatory risk for the whole group. Bad news can also spill over in the same direction if it reveals shared exposure to weaker demand, higher costs, or sector-wide legal risk. Under competitive substitution, by contrast, the news changes relative advantage within the industry. A firm-specific win may hurt rivals, while a firm-specific setback may benefit them.

The mechanisms are not mutually exclusive. A strong earnings report from a semiconductor firm can simultaneously signal broad AI demand and relative product leadership. A regulatory action against a bank can imply both common sector scrutiny and firm-specific customer migration. The empirical question is therefore not whether every article is purely industry-wide or purely firm-specific. It is whether the average pattern in competitor returns is more consistent with same-direction contagion or with opposite-direction substitution once articles are classified systematically.

Studying that question is difficult with raw news alone. Ticker-linked news feeds contain a mix of clean corporate events, analyst notes, macro commentary, generic market roundups, and articles that mention a tracked ticker only incidentally. Simple keyword filters can remove obvious junk, but they are poorly suited to deciding whether an article is materially relevant for the focal ticker set, whether it is sector-wide or firm-specific, and whether the expected competitor effect is same-direction or opposite-direction. That motivates the use of an LLM-based classification layer.

The LLM is useful here because it turns unstructured text into structured research variables. Instead of treating all ticker mentions as equally informative, the project classifies articles by relevance, relevance type, event type, sentiment, scope, expected competitor effect, materiality, and confidence. That improves measurement in two ways. First, it creates a cleaner event set for the return analysis. Second, it maps qualitative business interpretation into explicit categories that can be tested against abnormal returns rather than left implicit in prose.

This design fits naturally within the event-study tradition in finance. Event studies use abnormal returns to test whether new information is associated with unusual stock-price movement relative to a benchmark (Fama et al., 1969; Brown & Warner, 1985; MacKinlay, 1997). The present project extends that logic from focal firms to competitor networks. The target is not the direct price reaction of the company in the headline, but the reaction of rival firms in the same predefined competitive group.

The central research question is therefore: when materially relevant corporate news is released about a public company, how do the stocks of direct competitors respond, and are those responses more consistent with industry contagion or with competitive substitution?

The analysis is organized around three hypotheses:

- H1: Relevant corporate news is associated with measurable abnormal returns among competitor firms.
- H2: News classified as industry-wide or same-direction contagion is associated with same-direction competitor stock reactions.
- H3: News classified as firm-specific competitive advantage is more likely to generate opposite-direction competitor stock reactions.

The prior expectation is that short-run co-movement may be more common than pure winner-loser substitution, because many articles bundle firm information with sector information. The empirical analysis does not assume that result in advance. Instead, it asks whether the realized return evidence favors contagion once the news content has been converted into auditable labels.

## 2. Data Collection & Basic Analysis

The starting point is a ticker-based corporate news archive collected for a fixed universe of public firms. The normalized news dataset contains 55,094 ticker-level rows over 2025-06-26 to 2026-06-21. Each row stores the queried ticker, publication date, title, summary, URL, publisher, and source metadata. Because the feed is ticker based rather than article based, the same underlying story can appear more than once when the provider links it to multiple firms in the tracked universe. That duplication is economically useful in a spillover study because one article may legitimately concern several firms at once.

The preprocessing step is deliberately conservative. It removes rows with missing core text fields, missing summaries, extremely short summaries, malformed text, and exact ticker-level duplicates, but it does not try to infer economic relevance. In the realized data, that stage removes 2,556 rows and leaves 52,538 cleaned ticker-level observations. The purpose is to protect downstream text analysis from obviously unusable records without collapsing the candidate event set too early.

The next step is article-level deduplication. The deduplicated article dataset contains 38,131 unique articles, down from 52,538 cleaned ticker-level rows. This means deduplication avoids 14,407 repeated article classifications. The structure matters because the same article can later be classified once and then mapped back to all linked source tickers. In other words, the project separates the expensive interpretation task from the many-to-many article-ticker linkage needed for spillover analysis.

[[FIGURE1_DATASET_CONSTRUCTION]]

Competitor definitions are fixed ex ante. The project tracks five groups chosen for visible product-market overlap and dense public news coverage.

**Table 2. Competitor Groups**

| Group | Tickers |
| --- | --- |
| autos/EV | TSLA, GM, F, RIVN |
| semiconductors/AI | NVDA, AMD, INTC, QCOM, AVGO |
| airlines/travel | DAL, UAL, AAL, LUV |
| banks/finance | JPM, BAC, C, WFC |
| big tech/cloud | AAPL, MSFT, GOOGL, META, AMZN |

These groups define a 22-ticker query universe. They were selected precisely because both contagion and competition are plausible within them. Airlines share fuel and travel demand conditions, semiconductors share technology and demand cycles, banks share macro and regulatory exposure, and large platform firms often face both common and rival-specific shocks.

Because the unique-article universe is unevenly distributed across sectors and article styles, the project does not classify articles through a simple random draw. Instead, it constructs broad strata by combining industry buckets with coarse article buckets such as firm events, analyst or earnings news, macro or policy coverage, market-roundup or advice pieces, and other unclear cases. Sparse combinations are collapsed to keep cell sizes workable, producing 25 final strata. The final sample draws 50 articles from each stratum, generating a balanced classified input of 1,250 articles. This is a structured sample, not a full-population classification of all 38,131 unique articles.

That choice is important for interpretation. The classified sample is designed to preserve cross-sector coverage and prevent high-volume technology or firm-event stories from dominating the LLM stage. It also keeps API usage within project scope while still producing enough labeled events for descriptive and regression analysis. All 1,250 sampled articles were successfully classified, and 930 were judged relevant. The remaining 320 were retained as explicit not-relevant cases rather than dropped silently, which makes the filtering process auditable.

Overall, Section 2 establishes the basic data logic of the paper. The raw dataset is broad and noisy; preprocessing reduces technical noise; deduplication avoids redundant LLM calls; competitor groups define the economic neighborhoods of interest; and stratified sampling makes the classified set more balanced than an unconstrained draw would have been. The next section explains how the LLM layer converts those 1,250 sampled articles into structured variables for empirical use.

## 3. Application of LLM Models

The project's text-analysis problem is not collection but interpretation. Even after cleaning and deduplication, the sampled news set still mixes clean firm events with macro commentary, analyst pieces, and generic market roundups. Rule-based filters can capture obvious strings such as "earnings" or "Fed," but they do not reliably identify whether an article is economically relevant to the ticker set, whether it is firm-specific or industry-wide, or whether the expected spillover to rivals should be same-direction or opposite-direction. For that reason, the project uses an LLM as a structured classification layer between the article text and the event-study panel.

The classification workflow is reproducible and auditable. The final successful run used the `gpt-5.4-mini` model and a fixed prompt with structured JSON output. The request design used a two-message input consisting of the fixed system prompt and a user message containing a standardized article JSON record. No fine-tuning was performed. This was prompt-engineered classification through the API using structured output. The corresponding scripts, prompt file, and intermediate datasets are included in the submitted code archive.

The run used temperature `0.0` together with a strict output schema. The schema maps directly into the paper's economic question. Each article receives labels for relevance, relevance type, primary company, primary industry, event type, target-company sentiment, news scope, expected competitor effect, materiality, confidence, and a short reasoning field. The implementation validates outputs against enumerated allowed values, which reduces drift in category definitions and makes the labeled file easier to audit and analyze.

The first gatekeeping field is relevance. This matters because ticker-linked news collection is inherently noisy: a tracked ticker can appear in ETF advice, broad market recaps, or commentary focused on another company. Relevance is then refined through labels such as target company news, relevant market roundups, competitor company news, industry news, macro-policy news, and not relevant.

[[FIGURE2_LLM_RELEVANCE_DISTRIBUTION]]

Figure 2 shows why the LLM stage is necessary. Roughly one quarter of the classified sample survives technical cleaning but still fails the economic relevance screen. At the same time, the relevant set is not homogeneous. It contains clean focal-firm news, generic but still usable market roundups, sector news, and macro-policy events. That distinction later matters for robustness, especially when the strict sample removes relevant market roundups.

The paper's main interpretive variable is expected competitor effect. Same-direction contagion is used when the article appears to reveal common information likely to move rivals in the same direction. Opposite-direction competition is used when the article appears to shift relative competitive advantage. Other options, such as positive for competitors, negative for competitors, and neutral or no clear effect, allow the model to capture relevant cases that do not fit the core dichotomy cleanly. This variable is valuable because it turns a qualitative business interpretation into an ex ante label that can be checked against realized competitor returns.

Operationally, the workflow includes concurrency, retry logic, schema validation, resumability by article ID, and raw-response logging. The final file contains 1,250 successful classifications and 0 final error rows. That does not make the labels true by definition. It means the run completed cleanly and reproducibly. The labels remain research variables rather than objective facts, and borderline cases can still be debated. Still, the combination of a fixed prompt, structured output, explicit exclusions, and stored audit files makes the classification stage substantially more transparent than an ad hoc reading of headlines would be.

In short, the LLM does not replace financial reasoning. It standardizes the intermediate judgment step between raw language and empirical variables. Section 4 then shows how those labels are linked to price data to build the competitor event panel.

## 4. Event-Study Methodology

The event-study design links article-level LLM labels to short-run competitor returns. It follows standard daily event-study logic but applies it to rivals rather than only to focal firms. The key question is whether competitor stocks display abnormal movement after a news article is published about a firm in the same predefined group.

Daily prices were collected through yfinance for the 22 tracked firms plus SPY and QQQ. SPY is the main market benchmark because it provides a broad market proxy for abnormal-return construction. The stored price dataset contains 6,360 daily rows over 2025-05-30 to 2026-06-18. Returns are computed from adjusted close prices, which is the appropriate choice when stock splits and dividend adjustments matter.

The main abnormal-return measure is SPY-adjusted simple return:

`AR_{i,t} = R_{i,t} - R_{SPY,t}`

The core outcomes used in the report are next-day competitor abnormal return, competitor `CAR(0,1)`, and competitor `CAR(1,3)`. The first is the competitor's next-trading-day abnormal return. The second is the cumulative abnormal return over event day and the next day. The third is the cumulative abnormal return from one to three trading days after the event. The `t1` window is treated as the cleanest baseline because publication dates are available but reliable intraday timestamps are not.

Event-date handling therefore follows a conservative rule. Each article date is mapped to the next available trading day in the SPY calendar. If the article date is already a trading day, it becomes `t_0`; if it falls on a weekend or market holiday, the event shifts forward to the next session. This avoids pretending that all stories hit the market before the same-day close.

The event panel is built at the article-source-competitor level. The source ticker is the ticker linked to the article in the original collection stage, while the competitor ticker is another firm in the same predefined group. Source and competitor are never allowed to be the same row. This structure operationalizes the spillover question directly: a Delta-linked article can generate rows for United, American, and Southwest; an Nvidia-linked article can generate rows for AMD, Intel, Qualcomm, and Broadcom.

Panel expansion matters quantitatively. The 930 relevant articles map to 1,351 unique article-source events and then expand to 4,544 competitor-panel rows. Some late events do not have full post-event coverage through `t_3`, so usable row counts vary slightly by return outcome. The methodology keeps those missing values explicit rather than forcing complete windows for every observation.

### Empirical Regression Model

The financial model is an event-study regression, not a machine-learning return predictor. Abnormal returns are defined relative to the market benchmark, and cumulative abnormal returns aggregate those benchmark-adjusted moves over short windows:

`CAR_{i,[0,1]} = AR_{i,t_0} + AR_{i,t_1}`

`CAR_{i,[1,3]} = AR_{i,t_1} + AR_{i,t_2} + AR_{i,t_3}`

The main regression specification is:

`Y_{e,i} = alpha + beta_1 Label_e + gamma' Controls_{e,i} + epsilon_{e,i}`

Here, `Y_{e,i}` is the abnormal-return outcome for competitor `i` around article event `e`. Depending on the specification, the outcome can be next-day abnormal return, `CAR(0,1)`, or `CAR(1,3)`. `Label_e` is an LLM-generated article category, such as industry news or same-direction contagion. The control vector contains categorical article or industry controls used in the specification. Standard errors are clustered at the article level when feasible, and robust standard errors are used otherwise. The goal is interpretation of spillover mechanisms, not black-box out-of-sample return prediction.

The report uses three nested empirical samples derived from the LLM labels.

**Table 4. Event Sample Definitions**

| Sample | Rule | Panel rows |
| --- | --- | ---: |
| Broad sample | All relevant event-panel rows | 4,544 |
| Strict sample | Broad sample excluding relevant market roundups | 2,973 |
| Very strict sample | Strict sample plus materiality >= 3 and confidence >= 4 | 2,273 |

These definitions are economically important. The broad sample is the fullest view of relevant events, but it includes articles that are relevant while still somewhat generic. The strict sample asks whether the main patterns survive after removing those weaker market-roundup cases. The very strict sample then asks whether the signal remains when attention is restricted to the more material and more confidently classified events.

The statistical analysis is intentionally simple. Section 5 first compares mean abnormal returns across key LLM labels and then estimates linear regressions in which competitor abnormal returns are explained by structured article categories. The main explanatory blocks are relevance type, expected competitor effect, target-company sentiment, and primary industry. The empirical implementation uses OLS with clustered standard errors at the article level whenever clustering is feasible, and HC3 robust errors otherwise.

This design is exploratory rather than fully causal. It is built to test whether text-based event labels line up with short-run competitor returns in a disciplined way, not to prove a unique mechanism. Within that scope, the event-study framework is appropriate because it combines transparent return construction, conservative timing, and an event panel aligned with the rival-firm question.

## 5. Empirical Results

The broad sample contains 4,544 panel rows generated from 930 relevant classified articles and 1,351 unique article-source events. The strict sample contains 2,973 rows, and the very strict sample contains 2,273 rows. Because a small number of late events lack full return coverage, the usable outcome counts are slightly smaller than the raw panel counts. The key descriptive point, however, is that the event set is large enough to study common categories such as industry news and same-direction contagion, but thin for competition-oriented labels.

[[TABLE5_MAIN_EMPIRICAL_RESULTS]]

Table 5 compresses the central message of the paper. The cleanest next-day result is the industry-news coefficient, which is positive and statistically significant in both the broad and strict samples. That finding lines up with the core contagion story: when the article is classified as carrying industry-level information, competitors tend to move in the same direction on the next trading day even after conditioning on industry controls.

The second major result concerns same-direction contagion. In the next-day regressions the signal is positive but not always conventionally significant, which is unsurprising given the noise of daily stock returns. In the cumulative `CAR(1,3)` window, however, the coefficient is positive in both broad and strict specifications and becomes stronger in the strict sample. This is important substantively. It suggests that the contagion pattern is not just a same-day or one-day artifact and that it survives the removal of looser market-roundup observations.

[[FIGURE3_MEAN_RETURN_BY_EXPECTED_EFFECT]]

Descriptive means point in the same direction. Figure 3 plots the broad-sample mean next-day competitor abnormal return by expected competitor-effect label. Same-direction contagion is the dominant expected-effect label in the broad panel, with 3,093 rows and a mean next-day abnormal return of 0.0027. Its mean `CAR(0,1)` is 0.0048 and its mean `CAR(1,3)` is 0.0057. Those are modest return magnitudes, but they are economically meaningful in a short-horizon event-study setting and much more credible than a large mean computed from only a handful of events.

The relevance-type means reinforce the same interpretation. Industry news is the strongest broad-sample relevance category, with a mean next-day competitor abnormal return of 0.0066 and a mean `CAR(1,3)` of 0.0088. By comparison, target company news is only 0.0007 on the next day, while competitor company news is close to zero. This gap is consistent with theory. If the spillover channel is mainly shared information, the largest competitor response should appear when the article is explicitly interpreted as sector relevant rather than as a narrow focal-firm update.

The strict sample is the most useful robustness check because it removes relevant market roundups, the category most likely to blur the line between meaningful news and generic commentary. The main findings survive that restriction. The industry-news coefficient is effectively unchanged at 0.0062 with a `p`-value of 0.0031. The same-direction-contagion `CAR(1,3)` coefficient rises from 0.0113 to 0.0149 and becomes more statistically persuasive. That pattern matters because it reduces the concern that the headline results are driven by broad recaps rather than by cleaner event information.

The competition-oriented evidence is materially weaker. In mean-return space, opposite-direction competition looks large: the broad-sample next-day mean is 0.0072, and the broad `CAR(0,1)` mean is 0.0128. But those values are based on only 39 broad rows and 8 unique articles, with just 27 strict rows remaining after the market-roundup exclusion. The regression rows in Table 5 tell the right story: the sign is positive, but the estimate is statistically imprecise and too sparse to support a strong substitution claim. This is exactly why the report treats competitive substitution as plausible but not well identified in the realized sample.

Negative-for-competitors provides some additional directional evidence, but it is not central enough to justify another row in the compact table. In the broad descriptive table it has the lowest mean next-day abnormal return at about `-0.0009`, and in the strict sample it becomes more negative, which is directionally sensible. Still, the category is small relative to the contagion cases, so it does not overturn the broader reading of the data.

Across the broader descriptive tables, the event mix also supports caution in interpretation. The sample contains many market-roundup and macro-related events, not just clean firm announcements. That makes it unrealistic to expect every competitor effect to look like textbook substitution. It also helps explain why the strongest and most stable results emerge for labels designed to capture common-information channels rather than firm-specific winner-loser stories.

Taken together, the results are more consistent with short-run industry contagion than with pure competitive substitution. The strongest regression evidence is attached to industry news on the next day and to same-direction contagion in the longer `CAR(1,3)` window, especially in the stricter sample. Competition-style patterns do appear, but they are too rare and too statistically unstable to carry the paper's main conclusion. The appropriate interpretation is therefore asymmetric: the project finds meaningful evidence in favor of contagion, while the evidence for substitution remains suggestive rather than decisive.

## 6. Discussion, Limitations & Conclusion

The main substantive conclusion is straightforward. News about one firm often appears to transmit information that investors apply to nearby firms in the same sector. The evidence is strongest when the article is classified as industry news or as implying same-direction contagion, and it remains visible after excluding the looser market-roundup cases. This is the pattern one would expect if many corporate news events reveal shared information about demand, technology, regulation, financing conditions, or industry sentiment.

That interpretation is economically intuitive. Firms in the same competitor group rarely face fully independent environments. Airlines share fuel and travel demand conditions; semiconductor firms share technology cycles and capital-spending exposure; banks share macro and regulatory shocks. When a news article updates beliefs about those common conditions, rival stocks can move in the same direction even if the article names only one company explicitly.

The weaker evidence for competitive substitution does not mean the mechanism is absent. Some events should, in principle, redistribute expected profits across direct rivals. A product win, contract award, or operational setback at one firm can benefit competitors in the opposite direction. The problem in this project is empirical rather than theoretical: the clean substitution-style labels are infrequent, their row counts are small, and their estimates are therefore unstable. The results are consistent with the idea that competition effects exist but are harder to isolate cleanly than broader sector spillovers.

The project also makes a methodological point. It shows that an LLM can be used as a structured classification layer in an empirical finance pipeline without replacing conventional event-study logic. The model does not estimate returns and it does not prove causality. Its role is to convert messy news text into auditable labels that can be linked to abnormal-return outcomes. In that sense, the contribution is not "AI predicts markets." It is that prompt-engineered, schema-constrained classification can improve event definition in a setting where simple keyword methods are too crude.

Several limitations remain important. First, the LLM-classified set is a balanced sample of 1,250 articles, not the full universe of 38,131 unique articles. The results therefore describe a structured sample rather than an exhaustive one-year population of corporate news. Second, timing is daily rather than intraday. Publication dates are available, but reliable before-close versus after-close timestamps are not, so the analysis appropriately leans on next-trading-day and short-window returns. Third, the labels can contain classification noise even with a fixed prompt and structured outputs. Borderline distinctions between firm-specific, sectoral, and macro stories are inherently judgmental.

Fourth, some relevant articles are still broad by construction. The existence of relevant market roundups is a feature, not a bug, because it makes that ambiguity explicit. The strict and very strict samples partly address this issue, but they do not eliminate all mixed-scope events. Fifth, the competitor sets are predefined and limited to selected large listed firms, which keeps the project tractable but abstracts from broader industry ecosystems. Sixth, the event-study design is exploratory. It documents short-run associations between structured news labels and competitor abnormal returns, but it cannot fully rule out overlapping information arrivals or other confounds.

These limitations point to clear extensions. The most obvious next step is to classify a much larger share of the unique-article universe, ideally the full set. Intraday timestamps and intraday prices would improve event timing materially. Additional robustness work could compare alternative benchmarks, validate a subset of labels manually, or test whether the same patterns hold across other sectors and competitor definitions.

Within its scope, however, the project delivers a clear result. The evidence is more consistent with short-run industry contagion than with pure competitive substitution. Industry news is positive and statistically significant in the next-day regressions, same-direction contagion is positive and stronger in cumulative windows and stricter samples, and opposite-direction competition remains rare and imprecise. The broader implication is that corporate news often carries sector-level information that investors apply beyond the focal firm. More generally, the project shows that LLM-based classification can be integrated into a reproducible event-study workflow to study cross-firm news spillovers in equity markets.

## References

Brown, S. J., & Warner, J. B. (1985). Using daily stock returns: The case of event studies. *Journal of Financial Economics, 14*(1), 3-31.

Fama, E. F., Fisher, L., Jensen, M. C., & Roll, R. (1969). The adjustment of stock prices to new information. *International Economic Review, 10*(1), 1-21.

Loughran, T., & McDonald, B. (2011). When is a liability not a liability? Textual analysis, dictionaries, and 10-Ks. *The Journal of Finance, 66*(1), 35-65.

MacKinlay, A. C. (1997). Event studies in economics and finance. *Journal of Economic Literature, 35*(1), 13-39.

Tetlock, P. C. (2007). Giving content to investor sentiment: The role of media in the stock market. *The Journal of Finance, 62*(3), 1139-1168.
