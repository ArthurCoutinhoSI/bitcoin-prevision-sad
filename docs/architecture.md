# Architecture

## Overview

The application is one local Python project with two entry points:

- `btc_forecast.cli` — batch training, evaluation, persistence and inference.
- `app.py` — a read-only Streamlit presentation layer.

All state lives in files. `dc.csv` is the read-only input; `artifacts/` holds generated outputs.
There is no database, server process beyond Streamlit, authentication, cloud resource or network
call after dependency installation.

## Layers and dependency direction

```text
presentation        app.py  ──────────────┐
                    btc_forecast/dashboard/data.py
                                          │
application         btc_forecast/pipeline.py, cli.py
                                          │
domain              data.py, preprocessing.py, model.py,
                    evaluation.py, persistence.py, insights.py
                                          │
foundation          config.py
```

Dependencies point downward. Domain modules never import Streamlit or Altair. The dashboard data
module imports domain modules only, so it can be tested without a Streamlit runtime.

## Module responsibilities

| Module | Responsibility | Must not |
|--------|----------------|----------|
| `config.py` | Column names, target, horizon, split ratio, ARIMA grid, artifact names/version, disclaimer, limitations | Contain logic or I/O |
| `data.py` | Read CSV, normalise the unnamed date column, validate schema/numeric/positive values, compute a SHA-256 fingerprint | Clean, sort or impute |
| `preprocessing.py` | Sort ascending, remove exact duplicates, fail on conflicting dates, forward-fill prices, exclude leading missing closes, validate OHLC, build `PreprocessingSummary` | Fit or forecast |
| `model.py` | Build the series, chronological 80/20 split, AIC grid search on training only, fit, one-step walk-forward, production refit, next-day inference | Read files or persist |
| `evaluation.py` | Naive last-value baseline, MAE/MSE/RMSE/R², `EvaluationReport` assembly, baseline comparison | Modify the model or data |
| `persistence.py` | Atomic writes for the three artifacts, validated artifact loading, fingerprint/version/key/type checks | Train or evaluate |
| `insights.py` | Forecast direction and percentage change, baseline comparison text, data-quality text, limitations, disclaimer | Recommend an action |
| `pipeline.py` | Orchestrate load → clean → split → select → evaluate → refit → persist | Render or parse CLI arguments |
| `cli.py` | Parse `train`/`predict`, print summaries, map failures to exit codes | Contain model or data logic |
| `dashboard/data.py` | Load data and artifacts, assemble `DashboardView`, determine the five states | Import Streamlit or train |
| `app.py` | Cache resources, render header/forecast/charts/metrics/insights/disclaimer, empty and partial states | Train, tune, fabricate values or recommend actions |

## Training flow

```text
dc.csv
  └─ data.load_csv ──────────────► raw frame + Dataset (fingerprint, range)
       └─ preprocessing.clean ───► cleaned records + PreprocessingSummary
            └─ model.split ──────► ChronologicalSplit (first 80% / final 20%)
                 ├─ select_arima_order(train only, AIC grid)
                 ├─ walk_forward_predictions(validation, one step at a time)
                 ├─ baseline_predictions(previous actual)
                 └─ evaluation.build_report
                      └─ model.refit_production(all records)
                           └─ persistence.save_artifacts
                                ├─ model.pkl
                                ├─ evaluation.json
                                └─ validation_predictions.csv
```

An exception before `save_artifacts` leaves no new artifacts. During `save_artifacts`, each file
is written to a temporary file in the destination directory and atomically renamed; if any write
fails, files created by the same call are removed.

## Inference flow

`predict` loads `dc.csv` only to compute the expected fingerprint, then:

```text
persistence.load_model_artifact(model.pkl, expected_fingerprint)
  └─ model.forecast_next_day(artifact)
       └─ insights.build_forecast(...)
```

The model is never fitted during inference. The CLI prints text or the seven-field JSON object.

## Dashboard flow

```text
Streamlit cache_data ──► dashboard.load_dashboard_data(dc.csv)
Streamlit cache_resource ──► persistence.load_model_artifact(model.pkl, fingerprint)
        │
        └─ dashboard.load_dashboard_view(data=..., artifact=...)
             ├─ optional evaluation.json fingerprint check
             ├─ optional validation_predictions.csv read
             ├─ one next-day inference
             └─ DashboardView(status = ready | partial_artifacts | ...)
```

`app.py` renders the state. The `Reload data` button clears both caches and reruns the script.
Charts are rendered client-side by Altair, so hover, zoom and pan do not re-read artifacts.

## State model

| Status | Meaning | Rendered content |
|--------|---------|------------------|
| `ready` | Valid artifact, fingerprint match, forecast available | All sections |
| `partial_artifacts` | Valid model, optional evaluation or backtest file missing/unreadable | Forecast and metrics from the artifact; info message for the missing section |
| `missing_artifacts` | `model.pkl` absent | Empty state with training command; no forecast or metrics |
| `invalid_artifacts` | Corrupt, wrong version, missing keys, fingerprint mismatch or non-finite forecast | Plain-language reason and remediation; no forecast or metrics |
| `data_error` | `dc.csv` missing or unreadable | Actionable data error; no forecast |

## Design rules

- One responsibility per module; no speculative abstractions.
- Domain code is deterministic and free of UI imports.
- No hidden global state; the artifact is the single source of truth for model identity and
  metrics.
- All presentation values are derived from the dataset and artifact; failure states never show
  fabricated or zero-filled values.

## Requirements traceability

Every functional requirement and success criterion maps to implemented code and a task in
`specs/001-bitcoin-forecast-dashboard/tasks.md`.

### Functional requirements

| Requirement | Implementation | Tasks |
|-------------|----------------|-------|
| FR-001 | `data.load_csv` reads the first unnamed column as `date` | T010 |
| FR-002 | `data.load_csv` validates date and `close_USD` with actionable errors | T010 |
| FR-003 | `data.load_csv` numeric/positive checks; `preprocessing._validate_ohlc` | T010, T012 |
| FR-004 | `preprocessing.clean_dataset` sorts, deduplicates and fails on conflicts | T012 |
| FR-005 | `preprocessing.clean_dataset` forward-fills and excludes without future values | T012 |
| FR-006 | `PreprocessingSummary` counts, range and actions | T012 |
| FR-007 | `model.split_chronological` (80/20, no shuffle, training-only selection) | T016 |
| FR-008 | `model.select_arima_order` + `fit_arima` on `close_USD` only | T016 |
| FR-009 | `evaluation.baseline_predictions` over the same validation period | T017 |
| FR-010 | `pipeline` sets `next_forecast_date`; `model.forecast_next_day` | T019, T026 |
| FR-011 | `model.walk_forward_predictions` + `evaluation.compute_metrics` | T016, T017 |
| FR-012 | Artifact/report metadata: model, target, horizon, ranges, fingerprint | T018, T019 |
| FR-013 | `persistence.save_model_artifact` / `load_model_artifact` | T018, T025 |
| FR-014 | `load_model_artifact` validation + `predict` command; no fitting | T025, T026, T027 |
| FR-015 | `app.price_forecast_chart` with labeled forecast marker | T032 |
| FR-016 | Metrics table built from the stored evaluation report | T032 |
| FR-017 | `insights.build_insight` + dashboard insights panel | T026, T032 |
| FR-018 | `DISCLAIMER` rendered in header, insights and footer | T032, T033 |
| FR-019 | `missing_artifacts` state with no forecast or metrics | T031, T033 |
| FR-020 | Documented `train`, `predict` and `streamlit run` commands | T020, T027, T035 |
| FR-021 | No recommendation language in app/domain output; traced audit | T032, T034, T044 |
| FR-022 | `outperforms_baseline_rmse` stored and displayed honestly | T017, T032 |

### Success criteria

| Criterion | Evidence | Tasks |
|-----------|----------|-------|
| SC-001 | Training measured at 6.65 s (≤ 300 s) | T043 |
| SC-002 | Both metric sets with 200 observations in every report | T017, T021, T042 |
| SC-003 | Split 800/200 with training ending `2020-07-14` before validation `2020-07-15` | T016, T021, T042 |
| SC-004 | Predict-from-artifact integration test and CLI run, no retraining | T025, T026, T028 |
| SC-005 | Determinism test and two-run comparison within `1e-6` | T015, T042 |
| SC-006 | Ready-state AppTest shows forecast, metrics and disclaimer together | T030, T032, T034 |
| SC-007 | Cold Streamlit render measured at 2.45 s (≤ 5 s) | T043 |
| SC-008 | Missing/corrupt AppTest states show errors and no forecast | T029, T030, T033, T034 |
| SC-009 | `outperforms_baseline_rmse` present and rendered for every evaluation | T017, T032 |

### Scope audit summary

`app.py` and `btc_forecast/` contain no buy/sell/hold/recommendation/price-target/trading-signal
language and import no database, network, cloud, authentication, live-feed or trade-execution
dependency. Documentation mentions those terms only to state that they are out of scope. Runtime
dependencies are limited to the five pinned libraries; development dependencies to pytest and
Ruff.
