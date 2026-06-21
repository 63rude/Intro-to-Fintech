# Group Assignment - Project 2

Source: `Projects/Project 2/Data analysis project 2.pdf`

## Title

Data Analysis Project 2: Textual Analysis Using Large Language Models

## Type

Group project.

## Weight

20% of the course grade.

## Due Date

Due by the presentation day in week 9.

## Objective

Use Large Language Models to analyze textual data and generate inferences about firm outcomes, such as:

- Stock returns.
- Earnings surprises.
- Credit risk.
- ESG performance.
- Litigation risk.
- Innovation output.

The project emphasizes unstructured textual data, modern NLP techniques, and financial or economic interpretation. Unlike Project 1, the group has broad flexibility in topic, dataset, and methodology as long as the work uses LLMs and is grounded in an economic or financial framework.

Students are encouraged to use AI tools for coding and data collection. Routine or codifiable tasks may be delegated to AI or AI agents.

## Grading Method

The project is graded at the group level. It is worth 20%, based on completion and degree of perfection.

## Required Submission

- A zip file containing the program/code used for basic data collection and analysis.
- A report summary.

## Report Requirements

The written report has a maximum length of 20 pages and should include:

- Data description and preprocessing steps.
- Methodology, including LLM architecture, prompts, parameter settings, and training or fine-tuning if applicable.
- Empirical results and interpretation.
- Conclusion and limitations.

## Step-by-Step Requirements

### 1. Choose A Research Question

The research question should link textual data to a measurable economic outcome.

Examples:

- Does CEO tone in earnings calls predict firm performance?
- Can features extracted from patent descriptions forecast future technological breakthroughs?
- How does social media sentiment relate to stock return or volatility?
- Do LLM-based ESG scores predict changes in stock trading activity?

### 2. Select A Textual Dataset

Possible datasets:

- Corporate disclosures, financial statements, and earnings call transcripts.
- SEC EDGAR filings.
- Seeking Alpha transcripts.
- News articles from Dow Jones, Bloomberg, Factiva, or similar sources.
- Social media posts from Twitter/X, Reddit, or StockTwits.
- Patent filings from USPTO.
- Textual disclosures from Chinese-listed public firms.
- Government website disclosures.
- Self-constructed web-scraped datasets, if collected ethically and legally.

The handout says there is no required sample size because textual data access may be limited.

Available datasets upon request from the instructor:

- Earnings call transcripts with global coverage.
- US firms' patent descriptions.
- US firms' merger and acquisition announcements.
- Official task descriptions required by each job occupation.
- US firms' annual reports from `https://sraf.nd.edu/sec-edgar-data/lm_10x_summaries/`.

### 3. Preprocess And Prepare Data

Choose an approach such as:

- Embedding generation using open-source LLMs such as LLaMA or Mistral, or API-based models.
- Summarization or topic modeling.
- Sentiment scoring with finance-specific lexicons or fine-tuned LLM classification.
- Prompt-engineered LLM classification.

Example methods:

- Sentiment analysis.
- Topic modeling or clustering.
- Information extraction.
- Custom prompting or zero-shot learning.
- Embedding similarity analysis.

### 4. Connect To An Economic Or Financial Framework

The project must relate findings to theory or empirical literature, such as:

- Market efficiency.
- Information asymmetry and disclosure theory.
- Behavioral finance and investor sentiment.
- Risk factor models and asset pricing.
- Innovation and growth theories.

### 5. Run Empirical Testing

Link extracted textual features to firm outcomes using methods such as:

- Correlation tests.
- Simple regression.
- Panel data methods.
- Machine learning prediction models.

## Suggested Technical Resources

- `Projects/Project 2/LLM_Text_Analysis_Tutorial.pdf`
- `Projects/Project 2/LLM API.docx`
- DMXAPI model list and code examples PDF in `Projects/Project 2/`
- `Projects/Project 2/Additional resources for project 2 -- GitHub - AI4Finance-Foundation_FinNLP_ Democratizing Internet-scale financial data.pdf`
- Hugging Face models: `https://huggingface.co/models`
- DMXAPI model/code examples: `https://dmxapi.cn/models.html#code-block`
- Google Colab AI tutorial link in the handout

## Local Example Data Files

- `Projects/Project 2/textual data examples/10X Summaries _ SEC_EDGAR Data _ Software Repository for Accounting and Finance _ University of Notre Dame.pdf`
- `Projects/Project 2/textual data examples/Rent the Runway, Inc. (RENT) Q2 2025 Earnings Call Transcript _ Seeking Alpha.pdf`
- `Projects/Project 2/textual data examples/US20080010203A1_patent data.pdf`

## Local Reference Files

- `Projects/Project 2/references/Displacement_or_Augmentation_AI_Innovation_8_2025.pdf`
- `Projects/Project 2/references/Suggested reading - Use LLM to predict stock returns.pdf`

## Things To Watch

- Keep the financial question measurable.
- Document prompts and model settings clearly.
- Avoid treating LLM output as truth without validation.
- Make sure textual features are linked to actual outcomes.
- Include limitations, especially sample size, data bias, hallucination risk, and model reproducibility.
