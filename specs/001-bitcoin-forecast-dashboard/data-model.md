# Data Model: Bitcoin Forecast Dashboard

**Feature**: `001-bitcoin-forecast-dashboard` | **Date**: 2026-11-08

The system is file-based. There is no database; the source dataset and generated artifacts are the
persistence layer.

## Source Dataset

### DailyPriceRecord

One row from `dc.csv`.

| Field | Type | Rules |
|-------|------|-------|
| date | Date | Parsed from the first, unnamed column; unique; ascending after cleaning |
| open_USD | Float | Positive; required for OHLC validation when present |
| high_USD | Float | Positive; must be greater than or equal to open, low and close |
| low_USD | Float | Positive; must be less than or equal to open, high and close |
| close_USD | Float | Positive; required forecasting input and target |
| volume | Number | Non-negative when present; not used by the model |
| open_SAR / high_SAR / low_SAR / close_SAR | Float | Context only; not used by the model |

**Validation rules**:

- The file must contain a parseable date and `close_USD`.
- `close_USD` must be numeric and greater than zero.
- If all OHLC fields are present, each record must satisfy
  `low <= min(open, close) <= max(open, close) <= high`.
- Exact duplicate rows are removed and counted.
- The same date with conflicting values causes validation to fail.
- Missing price values are forward-filled; rows without a prior valid close are excluded.
- Future observations must never fill earlier values.

### Dataset

| Field | Type | Description |
|-------|------|-------------|
| source_path | String | Path to `dc.csv` |
| fingerprint | String | SHA-256 of the file contents |
| record_count | Integer | Number of accepted records |
| date_range | [Date, Date] | First and last accepted observation dates |
| records | List[DailyPriceRecord] | Chronologically ordered accepted records |

**Known source facts**: 1000 records covering 2018-05-07 through 2021-01-30, stored in descending
order, no missing values and no duplicate dates. The loader must still handle the general rules
above for future or replacement datasets.

### PreprocessingSummary

| Field | Type | Description |
|-------|------|-------------|
| source_count | Integer | Rows read from the file |
| accepted_count | Integer | Rows retained after validation and cleaning |
| rejected_count | Integer | Rows excluded |
| duplicates_removed | Integer | Exact duplicate rows removed |
| missing_values_imputed | Integer | Missing price values forward-filled |
| rows_excluded_without_prior_value | Integer | Rows excluded during imputation |
| date_range | [Date, Date] | Accepted observation range |
| actions | List[String] | Human-readable cleaning actions |

## Split

### ChronologicalSplit

| Field | Type | Description |
|-------|------|-------------|
| train_range | [Date, Date] | First 80% of accepted records |
| validation_range | [Date, Date] | Final 20% of accepted records |
| train_count | Integer | Number of training records |
| validation_count | Integer | Number of validation records |
| split_method | String | Always `chronological`; no shuffling |

**Invariants**:

- Training dates are strictly earlier than validation dates.
- The validation period is never used for ARIMA order selection.
- One-step-ahead validation predictions may use validation actuals only after each prediction is
  made, as part of the walk-forward procedure.

## Model

### ARIMAConfiguration

| Field | Type | Description |
|-------|------|-------------|
| order | [p, d, q] | Selected non-seasonal ARIMA order |
| selection_method | String | `AIC` over a fixed candidate grid |
| candidate_grid | Object | `p` in 0–2, `d` in 0–1, `q` in 0–2 |
| aic | Float | AIC of the selected model on training data |
| fitted_on | [Date, Date] | Training period used for selection and evaluation |

### ModelArtifact

Persisted to `artifacts/model.pkl`.

| Field | Type | Description |
|-------|------|-------------|
| artifact_version | Integer | Schema version; currently `1` |
| created_at | String | ISO-8601 timestamp |
| model | ARIMA result | Fitted production model |
| model_name | String | `ARIMA` |
| order | [p, d, q] | Selected order |
| target | String | `close_USD` |
| horizon_days | Integer | `1` |
| evaluation_training_range | [Date, Date] | 80% period used for evaluation |
| validation_range | [Date, Date] | 20% untouched evaluation period |
| production_training_range | [Date, Date] | Full dataset used for the production refit |
| last_observed_date | Date | Final date in the source dataset |
| next_forecast_date | Date | Day after `last_observed_date` |
| dataset_fingerprint | String | SHA-256 of the source file |
| preprocessing | PreprocessingSummary | Cleaning details |
| evaluation | EvaluationReport | Out-of-sample metrics and comparison |

**Compatibility rules**:

- `artifact_version` must equal the supported version.
- Required keys must be present and have the expected types.
- A dataset fingerprint mismatch is incompatible and must block inference.
- A missing, corrupt or incompatible artifact must produce a clear error.

## Evaluation

### ForecastPrediction

| Field | Type | Description |
|-------|------|-------------|
| date | Date | Predicted observation date |
| actual_close | Float | Actual close for validation rows; null for the future forecast |
| model_prediction | Float | ARIMA one-step-ahead prediction |
| baseline_prediction | Float | Naive last-value prediction |

### EvaluationMetrics

| Field | Type | Description |
|-------|------|-------------|
| mae | Float | Mean absolute error |
| mse | Float | Mean squared error |
| rmse | Float | Square root of MSE |
| r2 | Float or null | Coefficient of determination; null when the actuals have zero variance |
| observation_count | Integer | Number of one-step-ahead predictions |

### EvaluationReport

Persisted to `artifacts/evaluation.json`.

| Field | Type | Description |
|-------|------|-------------|
| generated_at | String | ISO-8601 timestamp |
| dataset_fingerprint | String | SHA-256 of the source file |
| split | ChronologicalSplit | Training and validation ranges |
| model | ARIMAConfiguration | Selected order and AIC |
| model_metrics | EvaluationMetrics | ARIMA metrics on validation |
| baseline_metrics | EvaluationMetrics | Naive baseline metrics on validation |
| outperforms_baseline_rmse | Boolean | Whether ARIMA RMSE is lower than the baseline |
| preprocessing | PreprocessingSummary | Cleaning summary |
| limitations | List[String] | Known interpretation limits |

### ValidationPredictionFile

Persisted to `artifacts/validation_predictions.csv`.

| Column | Type | Description |
|--------|------|-------------|
| date | Date | Validation observation date |
| actual_close | Float | Actual close |
| model_prediction | Float | ARIMA prediction |
| baseline_prediction | Float | Naive baseline prediction |

## Forecast and Insights

### Forecast

| Field | Type | Description |
|-------|------|-------------|
| target_date | Date | Day after the last observed date |
| predicted_close | Float | Production-model next-day prediction in USD |
| last_observed_close | Float | Last actual close in the dataset |
| direction | String | `up`, `down` or `flat` |
| percentage_change | Float | `(predicted_close - last_observed_close) / last_observed_close` |
| model_name | String | `ARIMA` |
| generated_at | String | ISO-8601 timestamp |

**Rules**: Direction is `up` when percentage change is greater than zero, `down` when less than
zero and `flat` when equal to zero. A non-finite prediction is an error.

### Insight

| Field | Type | Description |
|-------|------|-------------|
| direction | String | Forecast direction |
| percentage_change | Float | Forecast change relative to the last actual close |
| model_vs_baseline | String | Whether ARIMA beat the baseline on validation RMSE |
| data_quality | String | Record count, date range and cleaning summary |
| limitations | List[String] | Model and data limitations |
| disclaimer | String | Estimates only; not financial advice |

An insight is not a buy, sell or hold recommendation.

### DashboardView

| Field | Type | Description |
|-------|------|-------------|
| history | List[DailyPriceRecord] | Historical closing series for charting |
| forecast | Forecast or null | Next-day forecast; null in failure states |
| metrics | EvaluationReport or null | Model and baseline metrics; null in failure states |
| insights | Insight or null | Interpretation and disclaimer; null in failure states |
| validation_predictions | ValidationPredictionFile or null | Backtest rows; null when unavailable |
| metadata | Object | Artifact version, order, created-at, data/validation ranges, fingerprint |
| message | String | Plain-language state description |
| status | String | `ready`, `partial_artifacts`, `missing_artifacts`, `invalid_artifacts` or `data_error` |

## Lifecycle

```text
raw CSV
  -> validated Dataset
  -> cleaned records + PreprocessingSummary
  -> ChronologicalSplit
  -> ARIMA configuration selected on training
  -> evaluation model fitted on training
  -> one-step-ahead validation predictions
  -> EvaluationReport
  -> production model refit on all records
  -> ModelArtifact persisted
  -> artifact loaded by CLI or dashboard
  -> Forecast and Insight
```

**Failure states**:

- Invalid CSV, schema, prices or duplicates: stop before training with an actionable error.
- No ARIMA candidate fits: stop without writing a model artifact.
- Missing or corrupt artifact: stop inference and show the documented empty/error state.
- Artifact version or dataset fingerprint mismatch: refuse inference.
- Zero-variance validation actuals: report R² as null and continue.

## Persistence Formats

| Artifact | Format | Purpose |
|----------|--------|---------|
| `artifacts/model.pkl` | Pickle | Production model plus versioned metadata |
| `artifacts/evaluation.json` | JSON | Metrics, split, model configuration and data quality |
| `artifacts/validation_predictions.csv` | CSV | Validation actuals, ARIMA predictions and baseline predictions |

Artifacts are generated locally and excluded from version control.
