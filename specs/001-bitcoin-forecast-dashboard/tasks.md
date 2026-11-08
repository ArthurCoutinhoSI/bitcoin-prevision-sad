# Tasks: Bitcoin Forecast Dashboard

**Input**: Design documents from `specs/001-bitcoin-forecast-dashboard/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`

**Tests**: Included because constitution Principle V requires deterministic automated tests for
behavior changes. Tests are written first and must fail before the corresponding implementation.

**Organization**: Tasks are grouped by user story so each story can be implemented and validated
independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: `US1`, `US2`, `US3` — only used in user story phases
- Every task includes an exact file path or a command with explicit paths

## Path Conventions

Single project at the repository root: `btc_forecast/`, `app.py`, `tests/`, `docs/`, `artifacts/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the repository skeleton, pinned environment and deterministic fixtures.

- [X] T001 Create `btc_forecast/`, `btc_forecast/dashboard/`, `tests/unit/`, `tests/integration/`, `tests/fixtures/`, `docs/` and `artifacts/` directories, with empty `btc_forecast/__init__.py` and `btc_forecast/dashboard/__init__.py`
- [X] T002 Create `requirements.txt` with exactly `numpy==2.5.4`, `pandas==3.1.1`, `statsmodels==0.15.0`, `streamlit==1.67.0`, `altair==6.3.0` and `requirements-dev.txt` with exactly `pytest==9.2.0`, `ruff==0.17.4`
- [X] T003 [P] Create `.gitignore` excluding `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.ruff_cache/` and `artifacts/`
- [X] T004 [P] Create `tests/fixtures/dc_sample.csv` with 100 deterministic daily rows in descending date order, an unnamed first date column, consistent OHLC values and no duplicates; it must support an 80/20 split without touching `dc.csv`
- [X] T005 [P] Create `tests/fixtures/invalid_ohlc.csv` with one record that violates `low <= min(open, close) <= max(open, close) <= high`
- [X] T006 [P] Create `tests/fixtures/invalid_duplicate.csv` with two records for the same date that carry conflicting values
- [X] T007 Create `.venv` with `python3 -m venv .venv` (fallback: `uv venv .venv --python 3.13` when `ensurepip` is unavailable), then install `requirements.txt` and `requirements-dev.txt`; confirm imports of numpy, pandas, statsmodels, streamlit, altair, pytest and ruff

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Configuration, dataset loading and deterministic cleaning used by every story.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T008 Implement `btc_forecast/config.py` with `TARGET_COLUMN = "close_USD"`, `HORIZON_DAYS = 1`, `TRAIN_RATIO = 0.8`, `ARIMA_ORDER_GRID` of `p` in `[0, 1, 2]`, `d` in `[0, 1]`, `q` in `[0, 1, 2]`, `ARTIFACT_VERSION = 1`, and the artifact filenames `model.pkl`, `evaluation.json`, `validation_predictions.csv`
- [X] T009 [P] Write `tests/unit/test_data.py` covering: the first unnamed column is parsed as `date`; rows are returned for a valid file; SHA-256 fingerprints are stable and prefixed `sha256:`; a missing `close_USD`, non-numeric close, non-positive close or unparseable date raises an actionable error
- [X] T010 Implement `btc_forecast/data.py` with `load_csv(path)` returning the raw frame and dataset metadata (`source_path`, `fingerprint`, `record_count`, `date_range`, `records`); require a parseable date and numeric positive `close_USD`; reject invalid input with a message naming the file, column and offending value
- [X] T011 [P] Write `tests/unit/test_preprocessing.py` covering: ascending chronological order; exact duplicates removed and counted; conflicting duplicate dates fail; missing prices forward-filled and counted; rows without a prior valid close excluded and counted; the OHLC rule enforced; no future value fills a past value; summary fields `source_count`, `accepted_count`, `rejected_count`, `duplicates_removed`, `missing_values_imputed`, `rows_excluded_without_prior_value`, `date_range` and `actions`
- [X] T012 Implement `btc_forecast/preprocessing.py` with `clean_dataset(raw_frame)` returning cleaned records and a `PreprocessingSummary`; sort ascending by date, remove exact duplicates, fail on conflicting duplicate dates, forward-fill price columns, exclude rows without a prior valid close, and enforce `low <= min(open, close) <= max(open, close) <= high` whenever open, high and low are present

**Checkpoint**: Configuration, loading and cleaning are deterministic and tested; user stories can begin.

---

## Phase 3: User Story 1 - Train and validate a Bitcoin forecast (Priority: P1) 🎯 MVP

**Goal**: One documented run validates `dc.csv`, selects an ARIMA order on training data only,
evaluates one-step-ahead ARIMA and naive predictions on the untouched 20% validation period,
reports MAE/MSE/RMSE/R², refits on all records and writes the three artifacts.

**Independent Test**: Using only `dc.csv`, `python -m btc_forecast.cli train --data dc.csv
--artifacts artifacts` exits 0 and produces a validation-period evaluation report plus a binary
model artifact that unpickles and contains the fitted model.

### Tests for User Story 1 (write first, confirm failure, then implement)

- [X] T013 [P] [US1] Write `tests/unit/test_model.py` covering: the split keeps the first 800 of 1000 records for training and the last 200 for validation; no validation date precedes a training date; ARIMA selection uses AIC over `p` 0–2, `d` 0–1, `q` 0–2 on training data only; one-step-ahead predictions use only actuals available through the prior day; a scenario where no candidate fits raises a clear error
- [X] T014 [P] [US1] Write `tests/unit/test_evaluation.py` covering: the naive prediction equals the previous actual close; MAE, MSE, RMSE and R² formulas match hand-computed values; R² is `None` when validation actuals have zero variance; `observation_count` equals the number of predictions; `outperforms_baseline_rmse` equals `model_rmse < baseline_rmse`
- [X] T015 [P] [US1] Write `tests/integration/test_pipeline.py` for the training pipeline using `tests/fixtures/dc_sample.csv` and a temporary artifact directory: exit code 0, all three artifacts exist, `evaluation.json` contains both metric sets and 20 validation observations, `validation_predictions.csv` has ascending unique dates, `model.pkl` unpickles to a dictionary with `artifact_version == 1`, and two runs produce metrics equal within `1e-6`

### Implementation for User Story 1

- [X] T016 [US1] Implement `btc_forecast/model.py` with `split_chronological(records, train_ratio=0.8)`, `select_arima_order(train_series)` fitting the fixed grid and returning the lowest-AIC order, `fit_arima(series, order)`, `walk_forward_predictions(train_series, validation_series, order)` producing one-step-ahead predictions, and `refit_production(all_series, order)`; fail with an actionable error when every candidate fails
- [X] T017 [US1] Implement `btc_forecast/evaluation.py` with the naive last-value baseline, `compute_metrics(actuals, predictions)` for MAE/MSE/RMSE/R² including `None` for zero-variance actuals, and `build_evaluation_report(...)` containing `generated_at`, `dataset_fingerprint`, `split`, `model`, `model_metrics`, `baseline_metrics`, `outperforms_baseline_rmse`, `preprocessing` and `limitations`
- [X] T018 [US1] Implement artifact writes in `btc_forecast/persistence.py`: `save_model_artifact(path, payload)` with `artifact_version`, `created_at`, `model`, `model_name`, `order`, `target`, `horizon_days`, `evaluation_training_range`, `validation_range`, `production_training_range`, `last_observed_date`, `next_forecast_date`, `dataset_fingerprint`, `preprocessing` and `evaluation`; `save_evaluation_json(path, report)`; `save_validation_predictions(path, rows)`; each write goes to a temporary file in the same directory and is renamed into place, and any failure raises an artifact error without leaving partial files
- [X] T019 [US1] Implement `btc_forecast/pipeline.py` with `run_training(data_path, artifacts_dir)` executing load → clean → split → select order → fit evaluation model → one-step validation predictions → metrics → production refit → persist; return a summary with record counts, date ranges, order and metrics, and write no artifacts if an earlier step fails
- [X] T020 [US1] Implement the `train` subcommand in `btc_forecast/cli.py` with `--data` defaulting to `dc.csv` and `--artifacts` defaulting to `artifacts`; print the preprocessing summary, split counts, selected order, metric table and artifact paths; map invalid data/arguments to exit 2, no fitted candidate to exit 3, artifact failures to exit 4 and unexpected failures to exit 1
- [X] T021 [US1] Run `python -m btc_forecast.cli train --data dc.csv --artifacts artifacts` and verify exit 0, 1000 accepted records, 800/200 split, 200 validation predictions, finite metrics for both models, and an unpicklable `artifacts/model.pkl`; confirm `artifacts/evaluation.json` states whether ARIMA beat the baseline on validation RMSE

**Checkpoint**: User Story 1 works independently; training produces a complete evaluation and a reloadable artifact.

---

## Phase 4: User Story 2 - Reuse a persisted model for new forecasts (Priority: P2)

**Goal**: Load a persisted model, validate it and produce the next-day forecast without retraining,
with clear failures for missing, corrupt, incompatible or stale artifacts.

**Independent Test**: Starting from the artifact produced by User Story 1, `python -m
btc_forecast.cli predict --artifacts artifacts` returns a forecast for `2021-01-31` without
running training; a removed or corrupt artifact returns exit code 4.

### Tests for User Story 2 (write first, confirm failure, then implement)

- [X] T022 [P] [US2] Write `tests/unit/test_persistence.py` covering: a valid artifact round-trips; a missing file, non-pickle content, non-dictionary root, `artifact_version != 1`, missing required key, `order` without three non-negative integers and a dataset fingerprint mismatch each raise a distinct actionable error; a valid load produces a finite one-step forecast
- [X] T023 [P] [US2] Write `tests/unit/test_insights.py` covering: direction is `up` for positive change, `down` for negative change and `flat` for zero; `percentage_change` equals `(predicted_close - last_observed_close) / last_observed_close`; a non-finite prediction raises an error
- [X] T024 [US2] Extend `tests/integration/test_pipeline.py` with predict scenarios: after training, `predict` exits 0 without calling training; JSON output contains `target_date`, `predicted_close`, `last_observed_close`, `direction`, `percentage_change`, `model_name` and `generated_at`; predict against an empty artifact directory exits 4

### Implementation for User Story 2

- [X] T025 [US2] Implement `load_model_artifact(path, expected_fingerprint)` in `btc_forecast/persistence.py`; require an existing unpicklable file, a dictionary root, `artifact_version == 1`, every required key with the expected type, `order` of exactly three non-negative integers, a matching `sha256:` dataset fingerprint and a finite one-step forecast; raise a typed artifact error with a plain-language reason for each failure
- [X] T026 [US2] Implement `forecast_next_day(artifact)` in `btc_forecast/model.py` using the production model's one-step forecast, with `target_date` equal to the day after `last_observed_date` and a finite-price check; implement `build_forecast(...)` and `build_insight(...)` in `btc_forecast/insights.py` for direction, percentage change, baseline comparison, data quality, limitations and the disclaimer
- [X] T027 [US2] Implement the `predict` subcommand in `btc_forecast/cli.py` with `--artifacts` defaulting to `artifacts` and `--json`; print the human-readable summary or the seven JSON fields; never train or read `dc.csv` for fitting; map missing, corrupt, incompatible or fingerprint-mismatched artifacts to exit 4
- [X] T028 [US2] Run `python -m btc_forecast.cli predict --artifacts artifacts` and `--json`, verify exit 0 and `target_date` `2021-01-31`; then move `artifacts/model.pkl` aside and confirm exit 4 with an actionable message, restoring the file afterward

**Checkpoint**: User Stories 1 and 2 work independently; forecasting no longer requires training.

---

## Phase 5: User Story 3 - Review forecasts and insights on a dashboard (Priority: P3)

**Goal**: A local Streamlit dashboard loads the artifact, performs one next-day inference and shows
the forecast, history, metrics, validation backtest, insights and disclaimer without training.

**Independent Test**: `streamlit run app.py` with artifacts from User Story 1 shows the forecast for
`2021-01-31`, both charts, the metric table, insights and the disclaimer; removing the artifact shows
an actionable empty state with no fabricated forecast.

### Tests for User Story 3 (write first, confirm failure, then implement)

- [X] T029 [P] [US3] Extend `tests/unit/test_insights.py` covering: baseline-comparison wording matches validation RMSE; data quality text includes source, accepted, duplicate and imputation counts plus date range; limitations and disclaimer are present; insight text contains no buy, sell, hold, recommendation, price-target or trading-signal wording
- [X] T030 [P] [US3] Write `tests/integration/test_dashboard_data.py` covering `ready`, `missing_artifacts`, `invalid_artifacts`, `partial_artifacts` and `data_error`; assert no forecast or metrics are fabricated in failure states, a valid model plus missing `validation_predictions.csv` still yields forecast and metrics with a partial warning, and importing `btc_forecast.dashboard.data` does not import Streamlit

### Implementation for User Story 3

- [X] T031 [US3] Implement `btc_forecast/dashboard/data.py` with `load_dashboard_view(data_path, artifacts_dir)` returning a `DashboardView` containing history, forecast, metrics, insights and `status`; check the `dc.csv` fingerprint against the artifact, treat a missing model as `missing_artifacts`, a corrupt/incompatible/stale model as `invalid_artifacts`, a valid model with absent evaluation or backtest files as `partial_artifacts`, and unreadable data as `data_error`; keep this module free of Streamlit imports
- [X] T032 [US3] Implement `app.py` with `st.cache_resource` for the model and `st.cache_data` for data; render the header (title, target, horizon, ARIMA order, date range, fingerprint, artifact timestamp), forecast summary (target date, predicted close, last close, direction, percentage change), historical `close_USD` Altair line chart with a distinct labeled forecast marker on the same axes, metrics table with rows `ARIMA` and `Naive Last Value` and columns `MAE`, `MSE`, `RMSE`, `R²` (`N/A` for null), validation backtest chart with `Actual`, `ARIMA` and `Naive baseline`, insights panel, disclaimer and footer with the reproduction command
- [X] T033 [US3] Add the loading, `missing_artifacts`, `invalid_artifacts`, `partial_artifacts` and `data_error` states to `app.py`: show a spinner while loading; name the missing or invalid item and the remediation command; show no forecast, metrics or zero-filled placeholders in failure states; add a `Reload data` button that clears both caches; keep the disclaimer visible with the forecast
- [X] T034 [US3] Run `streamlit run app.py`, verify every required section, the hover/zoom/pan interactions, the forecast date `2021-01-31`, the disclaimer beside the forecast and the absence of recommendation language; then test the missing-artifact and partial-artifact states by moving `artifacts/model.pkl` and `artifacts/validation_predictions.csv` aside and restoring them afterward

**Checkpoint**: All three user stories work together; the dashboard is read-only and never trains.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, quality gates, performance and final scope verification.

- [X] T035 [P] Rewrite `README.md` as the single documentation entry point: purpose, scope, no buy/sell/hold positioning, setup with pinned dependencies, training, prediction, dashboard, test and lint commands, artifact description, limitations, and links to every file in `docs/`
- [X] T036 [P] Write `docs/architecture.md` describing the layer boundaries, module responsibilities, dependency direction and the rule that domain modules do not import Streamlit
- [X] T037 [P] Write `docs/data.md` documenting `dc.csv` provenance, the unnamed date column, the 1000-record range 2018-05-07 to 2021-01-30, OHLC and duplicate rules, forward-fill behavior, fingerprinting and data limitations
- [X] T038 [P] Write `docs/domain.md` documenting the forecast target and horizon, the 80/20 chronological split, ARIMA order selection on training only, one-step-ahead walk-forward evaluation, the naive baseline, MAE/MSE/RMSE/R² formulas, direction and percentage-change rules, and the no-recommendation boundary
- [X] T039 [P] Write `docs/operations.md` documenting setup, training, prediction, dashboard launch, exit codes 0–4, the five dashboard states, artifact regeneration, fingerprint mismatch recovery and the pickle trust restriction
- [X] T040 [P] Write `docs/decisions.md` recording the significant decisions and alternatives from `research.md`: pandas ingestion, no scaling, 80/20 split, training-only AIC selection, production refit, numpy metrics, pickle persistence, Streamlit with Altair, and rejected tools
- [X] T041 Run `.venv/bin/python -m pytest`, `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .` and `.venv/bin/python -m compileall -q btc_forecast app.py`; fix every failure without weakening tests or adding dependencies
- [X] T042 [P] Execute the 14 validation scenarios in `quickstart.md` in order and record any deviation; confirm determinism within `1e-6`, all artifacts, all failure states and offline operation
- [X] T043 [P] Measure the performance criteria: training at most 5 minutes, dashboard first content at most 5 seconds, model load at most 1 second and next-day inference at most 100 ms after load; record the measurements in `docs/operations.md`
- [X] T044 Perform a final scope and traceability audit: grep `app.py`, `btc_forecast/`, `README.md` and `docs/` for buy/sell/hold, recommendation, price-target and trading-signal language; confirm no database, API, cloud, auth, live feed or trade execution exists; map every FR-001 to FR-022 and SC-001 to SC-009 to an implemented task; update any stale documentation in the same change

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies; T001 and T002 precede T007.
- **Foundational (Phase 2)**: Depends on Setup; blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational.
- **User Story 2 (Phase 4)**: Depends on User Story 1 because it needs the artifact schema and a trained artifact for integration tests.
- **User Story 3 (Phase 5)**: Depends on User Story 1 for artifacts and User Story 2 for artifact loading and forecast generation.
- **Polish (Phase 6)**: Depends on all desired user stories.

### Task Dependencies

- T010 depends on T008 and T009; T012 depends on T008 and T011.
- T016 depends on T008, T010 and T012.
- T017 depends on T016; T018 depends on T016 and T017; T019 depends on T016–T018; T020 depends on T019.
- T021 depends on T013–T020.
- T025 depends on T018; T026 depends on T025; T027 depends on T025 and T026; T028 depends on T027.
- T031 depends on T025 and T026; T032 depends on T031; T033 depends on T032; T034 depends on T033.
- T041 depends on T035–T040; T042–T044 depend on T041.

### Within Each User Story

1. Write the listed tests and confirm they fail.
2. Implement models and pure domain functions.
3. Implement persistence or data assembly.
4. Wire the CLI or dashboard presentation layer.
5. Run the independent test before moving to the next story.

---

## Parallel Opportunities

### Setup

```bash
# After T001 and T002:
T003 .gitignore
T004 tests/fixtures/dc_sample.csv
T005 tests/fixtures/invalid_ohlc.csv
T006 tests/fixtures/invalid_duplicate.csv
```

### User Story 1

```bash
# Tests can be written together:
T013 tests/unit/test_model.py
T014 tests/unit/test_evaluation.py
T015 tests/integration/test_pipeline.py
```

### User Story 2

```bash
T022 tests/unit/test_persistence.py
T023 tests/unit/test_insights.py
```

### User Story 3

```bash
T029 tests/unit/test_insights.py
T030 tests/integration/test_dashboard_data.py
```

### Polish

```bash
T035 README.md
T036 docs/architecture.md
T037 docs/data.md
T038 docs/domain.md
T039 docs/operations.md
T040 docs/decisions.md
```

Parallel work must respect the dependencies above; tests and the code they exercise are not run
in parallel.

---

## Parallel Example: User Story 1 Test Cycle

```text
1. Write T013, T014 and T015 together and confirm all fail.
2. Implement T016, then T017, then T018.
3. Implement T019 and T020.
4. Run T021 against dc.csv and the full US1 test set.
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (T001–T007).
2. Complete Phase 2 (T008–T012).
3. Complete Phase 3 (T013–T021).
4. Stop and validate: run the training command against `dc.csv`, inspect the three artifacts and
   unpickle `model.pkl`.
5. The MVP delivers a validated forecast, a complete baseline comparison and a reusable model
   artifact. User Story 2 then demonstrates the reload path.

### Incremental Delivery

1. Setup + Foundational → deterministic data pipeline.
2. Add User Story 1 → training, evaluation, artifacts and metrics (MVP).
3. Add User Story 2 → artifact validation and next-day prediction without retraining.
4. Add User Story 3 → dashboard with charts, metrics, insights and states.
5. Polish → documentation, quality gates, performance and scope audit.

### Parallel Team Strategy

After Foundational, only US1 can start because US2 and US3 consume its artifact contract. Once US1
is complete, US2 and the documentation drafts can proceed in parallel, followed by US3. Within each
story, independent test files can be written concurrently.

---

## Task Summary

| Phase | Tasks | Count |
|-------|-------|-------|
| Setup | T001–T007 | 7 |
| Foundational | T008–T012 | 5 |
| User Story 1 (P1) | T013–T021 | 9 |
| User Story 2 (P2) | T022–T028 | 7 |
| User Story 3 (P3) | T029–T034 | 6 |
| Polish | T035–T044 | 10 |
| **Total** | | **44** |

## Notes

- Tests are included because the project constitution requires them; remove none without amending
  the constitution.
- Every behavior change must keep `README.md` and `docs/` current in the same task group.
- Do not add dependencies beyond the pinned runtime and development lists.
- Do not add buy, sell, hold, price-target or trading-signal output anywhere.
- Commit after each task or logical group; stop at each checkpoint to validate the story.
