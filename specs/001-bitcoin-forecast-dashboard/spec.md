# Feature Specification: Bitcoin Forecast Dashboard

**Feature Branch**: `N/A (no branch hook configured)`

**Created**: 2026-11-07

**Status**: Draft

**Input**: User description: "The project consists of training a predictive model using a chosen data source, and displaying the generated predictions and extracted insights on a dashboard to guide decision-making. The chosen dataset is dc.csv, which contains daily Bitcoin data from 2018 to 2021. Data preprocessing; predictive model using time series techniques; model evaluation with MAE, MSE/RMSE and R²; model persistence to a binary file for reuse."

## Clarifications

### Session 2026-11-07

- Q: How many forecasting techniques should the deliverable actually train and compare? → A: One allowed time-series model plus a naive last-value baseline.
- Q: How should the model generate predictions over the held-out period for evaluation? → A: One-step-ahead walk-forward with an 80% training and 20% validation chronological split; the validation period is the untouched final evaluation set.
- Q: Which historical inputs should the forecasting model use to predict the next-day closing price? → A: Closing price only.
- Q: Should the dashboard make an explicit buy, sell or hold recommendation, or only present the forecast and supporting insights? → A: Forecast and supporting insights only.
- Q: Must the selected model beat the naive baseline on the held-out period for the deliverable to be considered successful, or is a complete comparison enough? → A: Complete comparison only; no minimum performance threshold.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Train and validate a Bitcoin forecast (Priority: P1)

An analyst loads the historical Bitcoin dataset, runs the forecasting workflow, and receives a
validated next-day price forecast together with an evaluation report and a reusable model.

**Why this priority**: This is the core of the project. Without a trained, validated, and
persisted model, there is nothing to display on the dashboard or reuse.

**Independent Test**: Using only `dc.csv`, a single documented run produces cleaned data, a
validation-period evaluation report containing MAE, MSE, RMSE and R², and a reloadable binary
model artifact, with no manual intervention.

**Acceptance Scenarios**:

1. **Given** a valid `dc.csv`, **When** the training workflow runs, **Then** the dataset is
   validated, cleaned, ordered chronologically, and a preprocessing summary is produced.
2. **Given** cleaned data, **When** the model is trained, **Then** the model configuration is
   selected using only the training period, and one selected time-series technique plus a naive
   baseline are evaluated on the untouched 20% validation period using one-step-ahead predictions.
3. **Given** a completed evaluation, **When** the report is produced, **Then** it contains MAE,
   MSE, RMSE and R² for the selected model and the baseline over the validation period.
4. **Given** a successful training run, **When** it finishes, **Then** the trained model, its
   preprocessing configuration and its metadata are persisted in a binary artifact that can be
   reloaded.
5. **Given** the same dataset and configuration, **When** the workflow is run again, **Then** the
   reported metrics are identical within a tolerance of 1e-6.

---

### User Story 2 - Reuse a persisted model for new forecasts (Priority: P2)

An analyst reuses a previously trained model to generate the next forecast without retraining,
so results remain reproducible and the training cost is paid once.

**Why this priority**: Model persistence is an explicit project requirement and enables the
dashboard to serve forecasts without repeating training.

**Independent Test**: Starting from a valid persisted artifact, a fresh session loads the model
and produces a next-day forecast without accessing the training workflow.

**Acceptance Scenarios**:

1. **Given** a valid persisted artifact, **When** it is loaded, **Then** a forecast for the day
   after the last observed date is generated.
2. **Given** an artifact that is missing, corrupt or incompatible, **When** loading is attempted,
   **Then** a clear error is reported and no partial forecast is produced.
3. **Given** a reloaded artifact, **When** its metadata is inspected, **Then** the training and
   validation date ranges, preprocessing configuration and evaluation metrics are available.

---

### User Story 3 - Review forecasts and insights on a dashboard (Priority: P3)

An investor or analyst opens a dashboard and reviews historical prices, the next-day forecast,
model quality, data quality and plain-language insights to support a decision.

**Why this priority**: The dashboard is the decision-support interface, but it depends on the
forecast and evaluation produced by the higher-priority stories.

**Independent Test**: Launch the dashboard using artifacts produced by User Story 1 and verify
that the chart, forecast, metrics and insights are displayed without retraining.

**Acceptance Scenarios**:

1. **Given** forecast artifacts exist, **When** the dashboard opens, **Then** the historical
   closing price series and the next-day forecast are visible, with the forecast date clearly
   labeled.
2. **Given** evaluation results exist, **When** the dashboard is viewed, **Then** MAE, MSE, RMSE
   and R² are displayed for the selected model and the baseline.
3. **Given** forecast artifacts exist, **When** the dashboard is viewed, **Then** insights show
   the forecast direction and percentage change, the selected model versus the baseline, a data
   quality summary and the model's limitations.
4. **Given** no forecast artifacts exist, **When** the dashboard opens, **Then** an actionable
   empty state is shown and the application does not fail.
5. **Given** the provided dataset of 1000 daily records, **When** the dashboard opens, **Then**
   the initial content is visible within 5 seconds in the documented reference environment.

---

### Edge Cases

- The dataset is empty, unreadable or missing required columns.
- Dates are duplicated, out of order or cannot be parsed.
- Required prices are missing, non-numeric, non-positive or violate OHLC consistency.
- The dataset contains fewer observations than the selected model needs.
- The selected model cannot be fitted or produces non-finite forecasts.
- The validation period has too few observations for reliable model evaluation or R².
- A persisted model artifact is missing, corrupt, from another version or built with a different
  preprocessing configuration.
- The forecast target date already exists in the historical data.
- A forecast is requested for a horizon other than the next day.
- The dashboard is opened before training has produced artifacts.
- The dashboard is opened with only partially generated artifacts.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST load `dc.csv` from the repository root and interpret the first,
  unnamed column as the observation date.
- **FR-002**: The system MUST validate that the dataset contains a parseable date and the required
  USD closing price field, and MUST reject invalid input with a clear, actionable message.
- **FR-003**: The system MUST validate that required prices are numeric and positive; when open,
  high and low are present, each record MUST satisfy
  `low <= min(open, close) <= max(open, close) <= high`.
- **FR-004**: The system MUST order records chronologically, detect duplicate dates and report
  counts of removed exact duplicates; conflicting duplicates MUST cause validation to fail.
- **FR-005**: The system MUST handle missing required values with a documented, deterministic
  strategy, report how many values were imputed or excluded, and MUST NOT use future observations
  to fill past values.
- **FR-006**: The system MUST produce a preprocessing summary containing the source record count,
  accepted and rejected record counts, date range, missing-value actions and duplicate actions.
- **FR-007**: The system MUST split the series chronologically into training (first 80%) and
  validation (final 20%) periods without shuffling; the validation period is the untouched final
  evaluation set and MUST NOT be used for configuration selection.
- **FR-008**: The system MUST train exactly one time-series forecasting technique selected from
  the allowed family: moving averages, exponential smoothing, ARIMA or Prophet, using only the
  historical USD closing price series as input. Model configuration MUST be selected using only
  the training period.
- **FR-009**: The system MUST evaluate the selected model against a naive baseline that repeats
  the last observed closing price, using the same validation period.
- **FR-010**: The system MUST forecast the next-day closing price in USD, defined as the trading
  day immediately after the last date in the dataset.
- **FR-011**: The system MUST generate one-step-ahead predictions over the validation period and
  produce a tabular evaluation report containing MAE, MSE, RMSE and R² for the selected model and
  the baseline.
- **FR-012**: The system MUST record, for every evaluation, the model identity, target, forecast
  horizon, training and validation date ranges, and dataset fingerprint.
- **FR-013**: The system MUST persist the trained model, its preprocessing configuration and its
  metadata in a single binary artifact, and MUST provide a documented way to reload it.
- **FR-014**: The system MUST generate the next-day forecast from the persisted artifact without
  retraining and MUST refuse to forecast when the artifact is missing, corrupt or incompatible.
- **FR-015**: The dashboard MUST display the historical closing price series, the next-day
  forecast value and its target date on the same timeline.
- **FR-016**: The dashboard MUST display the evaluation table with MAE, MSE, RMSE and R² for the
  selected model and the baseline.
- **FR-017**: The dashboard MUST display insights covering forecast direction and percentage
  change, selected model versus baseline, data quality summary and known limitations.
- **FR-018**: The dashboard MUST display a visible notice that forecasts are estimates, are not
  guarantees and do not constitute financial advice.
- **FR-019**: The dashboard MUST display an actionable empty state when forecast artifacts are
  missing instead of failing or showing fabricated values.
- **FR-020**: The system MUST provide one documented command to run training plus evaluation and
  one documented command to launch the dashboard.
- **FR-021**: The dashboard MUST NOT display buy, sell or hold recommendations; it presents only
  the forecast, evaluation metrics and supporting insights.
- **FR-022**: The evaluation report MUST state whether the selected model outperformed the naive
  baseline on validation RMSE, without imposing a minimum performance threshold.

### Key Entities *(include if feature involves data)*

- **Daily Price Record**: One observation date and its Bitcoin open, high, low, close and volume;
  the USD closing price is both the sole forecasting input and the target, while OHLC and SAR
  values are context and validation only.
- **Dataset**: The ordered collection of daily price records loaded from `dc.csv`, with its date
  range, record count and validation outcomes.
- **Preprocessing Summary**: The record counts, date range, imputation actions, duplicate actions
  and rejected records produced before training.
- **Model Artifact**: The persisted binary representation of the trained model plus preprocessing
  configuration, model identity and training metadata.
- **Forecast**: The predicted next-day closing price in USD, its target date, the originating
  model and the generation timestamp.
- **Evaluation Metrics**: MAE, MSE, RMSE and R² computed for the selected model and the naive
  baseline over the same untouched validation period, using one-step-ahead predictions.
- **Insight**: A plain-language interpretation of the forecast direction, expected error, data
  quality and model limitations shown on the dashboard; it is not a buy, sell or hold
  recommendation.
- **Dashboard View**: The user-facing composition of historical series, forecast, metrics,
  insights and disclaimer.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can go from the provided `dc.csv` to a persisted model and evaluation report
  in a single documented run lasting no more than 5 minutes in the documented reference
  environment.
- **SC-002**: 100% of successful runs produce a validation-period report containing MAE, MSE,
  RMSE and R² for both the selected model and the naive baseline.
- **SC-003**: 100% of successful runs use an 80/20 chronological split, with zero validation dates
  earlier than any training date and zero validation observations used for training or
  configuration selection.
- **SC-004**: A persisted model can be reloaded and produce a next-day forecast without retraining
  in 100% of attempts with a valid artifact.
- **SC-005**: Repeating a run with the same dataset and configuration produces metrics identical
  within 1e-6 in 100% of attempts.
- **SC-006**: The dashboard displays the forecast, its target date, the evaluation metrics and the
  financial-advice disclaimer together in 100% of loaded views.
- **SC-007**: With 1000 daily records, the dashboard shows its initial content within 5 seconds in
  the documented reference environment.
- **SC-008**: 100% of empty-artifact and corrupt-artifact scenarios show an actionable message and
  produce no fabricated forecast.
- **SC-009**: 100% of completed evaluations state whether the selected model outperformed the
  naive baseline on validation RMSE; no minimum accuracy threshold is required for success.

## Assumptions

- The prediction target is the next-day closing price in USD; multi-day horizons, intraday prices
  and trading-volume forecasting are out of scope.
- The provided dataset is the authoritative source: 1000 daily records covering 2018-05-07 through
  2021-01-30, stored in descending date order, with no missing values and no duplicate dates.
- The first column of `dc.csv` is the date field even though its header is empty.
- The series is split chronologically into 80% training and 20% validation; configuration is
  selected using only the training period, and the untouched validation period is reserved for
  final evaluation.
- Evaluation uses one-step-ahead walk-forward predictions over the validation period, always using
  only actual observations available before each predicted day.
- Exactly one allowed time-series technique will be implemented, using only the historical USD
  closing price series as input, and a naive last-value baseline is always reported for
  comparison.
- Model success is judged by a complete and honest comparison against the baseline, not by a
  minimum accuracy threshold; a model that does not beat the baseline is still reported.
- Missing values, if present in future data, are handled by forward fill for prices and by
  exclusion when no prior valid observation exists; every action is reported.
- The dashboard is a local, single-user application with no authentication, no multi-user
  collaboration and no remote deployment requirement.
- The system uses only `dc.csv`; live market feeds, external APIs and additional datasets are out
  of scope.
- The system supports decisions only; it does not execute trades, connect to exchanges, issue
  buy/sell/hold recommendations or provide financial advice.
- The system remains a single runnable application; new services, databases or infrastructure are
  out of scope unless separately justified and approved.
- The reference environment for timing criteria is a machine with at least 4 GB of RAM and 2 CPU
  cores, running the documented setup.
- Portuguese or English presentation language may be chosen during planning, but all labels,
  metrics and disclaimers must be consistent across the dashboard.
