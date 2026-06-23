# Event Panel Validation

## Overall status

- Failing checks: 3.
- Warning checks: 1.
- Passing checks: 6.

## Check results

- `source_ticker_not_equal_competitor_ticker`: pass (0). Rows where `source_ticker == competitor_ticker`.
- `source_and_competitor_same_config_group`: pass (0). Rows where source/competitor group assignments disagree with `config/competitor_groups.yaml`.
- `broad_25_strata_only`: pass (0). Panel strata count=25; allowed strata count from final LLM file=25.
- `date_window_ordering`: warn (180). Rows with true ordering violations among fully observed dates=0; rows missing one or more window dates=180.
- `t1_is_next_trading_day_after_event_trade_date`: pass (0). Rows where `t1_date` is not exactly the next SPY trading day after `event_trade_date`.
- `abnormal_car_0_1_identity`: fail (62). Rows where `competitor_car_abret_spy_0_1` does not equal `competitor_abret_spy_t0 + competitor_abret_spy_t1`.
- `abnormal_car_1_3_identity`: fail (69). Rows where `competitor_car_abret_spy_1_3` does not equal `competitor_abret_spy_t1 + t2 + t3`.
- `raw_car_columns_identity`: fail (131). Rows failing raw CAR identities: 0_1=62, 1_3=69.
- `duplicate_article_source_competitor_rows`: pass (0). Duplicate rows by `article_id + source_ticker + competitor_ticker`.
- `sample_flag_consistency`: pass (0). Flag mismatches: broad=0, strict=0, very_strict=0.

## Sample counts

- `sample_broad_rows`: 4,544 rows. All relevant rows in the panel.
- `sample_strict_rows`: 2,973 rows. Rows excluding `market_roundup_but_relevant`.
- `sample_very_strict_rows`: 2,273 rows. Strict rows with `materiality >= 3` and `confidence >= 4`.

## Missing competitor outcomes by ticker

- `AMZN`: 136 missing values.
- `GOOGL`: 128 missing values.
- `MSFT`: 120 missing values.
- `QCOM`: 118 missing values.
- `AAPL`: 108 missing values.
- `AMD`: 106 missing values.
- `AVGO`: 104 missing values.
- `META`: 100 missing values.
- `INTC`: 86 missing values.
- `NVDA`: 58 missing values.

## Missing competitor outcomes by variable

- `competitor_abret_spy_t3`: 180 missing values.
- `competitor_ret_t3`: 180 missing values.
- `competitor_abret_spy_t2`: 149 missing values.
- `competitor_ret_t2`: 149 missing values.
- `competitor_abret_spy_t1`: 111 missing values.
- `competitor_car_1_3`: 111 missing values.
- `competitor_car_abret_spy_1_3`: 111 missing values.
- `competitor_ret_t1`: 111 missing values.
- `competitor_abret_spy_t0`: 49 missing values.
- `competitor_car_0_1`: 49 missing values.
- `competitor_car_abret_spy_0_1`: 49 missing values.
- `competitor_ret_t0`: 49 missing values.

## Notes

- The requested CAR identity checks were mapped to the abnormal-return CAR columns (`competitor_car_abret_spy_0_1` and `competitor_car_abret_spy_1_3`) because those are the fields that correspond to the abnormal-return components named in the request.
- The raw-return CAR columns (`competitor_car_0_1` and `competitor_car_1_3`) were also checked against their raw return components.
