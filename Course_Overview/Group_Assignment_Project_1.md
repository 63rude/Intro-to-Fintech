# Group Assignment - Project 1

Source: `Projects/Project 1/Data analysis project 1.pdf`

## Title

Data Analysis Project 1: Predicting Stock Returns Using Machine Learning

## Type

Group project.

## Weight

20% of the course grade.

## Objective

Develop a machine learning model that predicts stock returns using historical data and relevant financial indicators. The model should help provide insight into future stock price movements and support investor decision-making.

Students are encouraged to use AI tools for coding and data collection. Routine or codifiable tasks may be delegated to AI or AI agents.

## Grading Method

The project is graded at the group level. The 20% credit is based on degree of completion/perfection. Model performance also contributes to the grade, described as:

`Project completion rate * Percentized performance metrics for out-of-sample predictions`

## Required Submission

- A zip file containing the programs/code used for data collection and analysis.
- A written report summarizing:
  - Data collection process.
  - Feature selection.
  - Model selection.
  - Model performance.
  - Economic interpretation of important features and their effects on stock return.

## Project Goals

- Build predictive models for short-term and long-term stock returns.
- Engineer and select features that affect stock returns.
- Use historical price, volume, macroeconomic, and company-specific data.
- Backtest and validate model performance on historical and out-of-sample data.
- Deploy the model as an interactive tool or API for real-time predictions.

## Functional Requirements

### Data Collection

Possible sources:

- Yahoo Finance
- CRSP
- CSMAR
- Other reliable financial databases

Possible data types:

- Historical stock prices: open, high, low, close, adjusted close, volume.
- Technical indicators: moving averages, RSI, MACD.
- Fundamental data: earnings, dividends, P/E ratio.
- Macroeconomic indicators: interest rates, GDP growth, inflation.

Data frequency may be daily, weekly, or monthly depending on the prediction horizon.

### Data Preprocessing

- Clean missing data, outliers, and anomalies.
- Normalize or standardize variables.
- Create features such as lagged returns, volatility measures, and news sentiment variables.

### Model Development

Suggested model families:

- Linear regression, Lasso, Ridge.
- Random Forest, Gradient Boosting, XGBoost.
- RNN and LSTM.
- Support Vector Machines.

Training should focus on generalization and avoiding overfitting. Hyperparameter tuning can use grid search or Bayesian optimization.

### Model Evaluation

Suggested metrics:

- MSE
- MAE
- R-squared
- Sharpe Ratio
- F1 score

Validation should include backtesting, out-of-sample testing, and cross-validation.

## Suggested Tools

- Python
- TensorFlow or PyTorch
- Scikit-learn
- Pandas
- SQL databases
- Cloud services such as AWS, Azure, or GCP
- Google Colab

## Suggested References

- Gu, Kelly, and Xiu (2020), "Empirical asset pricing via machine learning."
- Leippold, Wang, and Zhou (2022), "Machine learning in the Chinese stock market."
- `Projects/Project 1/Machine learning in the Chinese stock market.pdf`
- `Projects/Project 1/Machine learning in the Chinese stock market_Appendix.pdf`
- `Projects/Project 1/ML_Stock_Returns_Tutorial_Full.pdf`

## Things To Watch

- Accuracy: acceptable predictive performance using R-squared, F1 score, or other appropriate metrics.
- Usability: output should be understandable and useful to investors.
- Performance: the model should handle the expected data size and prediction timing.
- Finance-specific validation: avoid random data splits that leak future information; use chronological splits where appropriate.
