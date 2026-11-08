# Implementation Plan: Bitcoin Forecast Dashboard

**Branch**: `001-bitcoin-forecast-dashboard` | **Date**: 2026-11-08 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-bitcoin-forecast-dashboard/spec.md` plus user
technical direction: Python, local `dc.csv`, Streamlit dashboard with interactive time-series
charts, pre-trained model inference, and a local ARIMA vs naive last-value evaluation pipeline.

## Summary

Build a single local Python application that validates and cleans `dc.csv`, selects a small ARIMA
configuration using only the 80% training period, evaluates one-step-ahead predictions on the
untouched 20% validation period against a naive last-value baseline, and reports MAE, MSE, RMSE
and R². After evaluation, the selected ARIMA order is refit on all available records to produce a
pickle-persisted production model. A Streamlit dashboard loads that artifact, performs next-day
inference locally, and presents interactive charts, metrics, data-quality insights, limitations
and a financial-advice disclaimer.

The implementation stays local and single-user. It adds no database, API server, authentication,
cloud resource, live market feed, trade execution or buy/sell/hold recommendation.

## Technical Context

**Language/Version**: Python 3.13.5 (verified locally); minimum Python 3.11.

**Primary Dependencies**: pandas 3.1.1, numpy 2.5.4, statsmodels 0.15.0, streamlit 1.67.0,
altair 6.3.0.

**Storage**: Read-only `dc.csv` input; generated local artifacts `artifacts/model.pkl`,
`artifacts/evaluation.json` and `artifacts/validation_predictions.csv`; no database.

**Testing**: pytest 9.2.0, Ruff 0.17.4 for lint/format, `python -m compileall` for syntax/build
verification.

**Target Platform**: Local Linux, macOS or Windows workstation; single user; no network access
required after dependency installation.

**Project Type**: Single project with a Python CLI and a Streamlit dashboard.

**Performance Goals**: Training plus evaluation completes in at most 5 minutes; dashboard first
render at most 5 seconds; model load at most 1 second; next-day inference at most 100 ms after
load.

**Constraints**: Only `dc.csv`; one ARIMA model plus the naive baseline; USD closing price only;
80% training and 20% validation; no test set; no live data, database, cloud, authentication,
trade execution or buy/sell/hold recommendation; deterministic results for identical input.

**Scale/Scope**: 1000 daily records, one forecast target, one model, one baseline, two dashboard
charts, one metrics table and one insights panel.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Result |
|-----------|------|--------|
| I. Simplicity and Maintainability | One package, small modules, no speculative abstractions, standard-library persistence | PASS |
| II. Separation of Responsibilities | Data, preprocessing, modeling, evaluation, persistence and insights do not import Streamlit; the dashboard is a presentation layer | PASS |
| III. Scope Control | Only the specified dataset, model, baseline, dashboard and CLI commands; no extra features | PASS |
| IV. Justified Dependencies and Infrastructure | Every runtime and development dependency is justified below; no new infrastructure | PASS |
| V. Verifiable Quality | Unit and integration tests, deterministic fixtures, lint, compile check and documented commands | PASS |
| VI. Complete and Current Documentation | README plus architecture, data, domain, operations and decision documents | PASS |
| Additional project constraints | One runnable application; `dc.csv` read-only; no secrets; decision support only | PASS |

### Dependency Justification

| Dependency | Scope | Why needed | Alternatives rejected |
|------------|-------|------------|-----------------------|
| numpy 2.5.4 | Runtime | Array operations and MAE/MSE/RMSE/R² formulas | Pure Python is slower and more error-prone for numeric work |
| pandas 3.1.1 | Runtime | CSV loading, date indexing, ordering and data-quality checks | Standard-library `csv` requires substantial manual parsing and date handling |
| statsmodels 0.15.0 | Runtime | Tested ARIMA implementation and one-step-ahead updating | `pmdarima` adds another dependency; Prophet is heavier; hand-written ARIMA is high-risk |
| streamlit 1.67.0 | Runtime | Requested local dashboard, caching and interactive UI | Flask plus JavaScript needs more code and dependencies; notebooks are not a dashboard |
| altair 6.3.0 | Runtime | Layered historical/forecast and backtest charts with hover and zoom | Native Streamlit charts cannot layer the forecast point cleanly; Plotly adds another chart library |
| pytest 9.2.0 | Development | Unit and integration tests with fixtures and temporary directories | `unittest` requires more boilerplate for the same coverage |
| Ruff 0.17.4 | Development | Lint and formatting gate required by the constitution | flake8 plus black plus isort requires multiple tools |

No additional model libraries, databases, web frameworks, cloud services, CI/CD, containers or
orchestration tools are introduced.

### Post-Design Re-Check

PASS. The design remains a single local application. Domain modules stay independent of
Streamlit. No dependency or infrastructure was added beyond those justified above. Tests and
documentation are part of the delivery.

## Project Structure

### Documentation (this feature)

```text
specs/001-bitcoin-forecast-dashboard/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── artifacts.md
│   ├── cli.md
│   └── dashboard.md
└── tasks.md              # Created later by /speckit.tasks
```

### Source Code (repository root)

```text
app.py                    # Thin Streamlit entry point
btc_forecast/
├── __init__.py
├── cli.py                # train and predict commands
├── config.py             # Paths, split ratios, ARIMA grid, artifact version
├── data.py               # CSV loading, validation, fingerprinting
├── preprocessing.py      # Cleaning, ordering, missing values, summary
├── model.py              # ARIMA selection, fitting, walk-forward forecasting
├── evaluation.py         # Baseline, metrics and evaluation report
├── persistence.py        # Pickle save/load, compatibility checks
├── insights.py           # Direction, change, comparison, limitations
├── pipeline.py           # End-to-end training/evaluation/persistence orchestration
└── dashboard/
    ├── __init__.py
    └── data.py           # Dashboard data assembly; no Streamlit imports in domain

tests/
├── unit/
│   ├── test_data.py
│   ├── test_preprocessing.py
│   ├── test_model.py
│   ├── test_evaluation.py
│   ├── test_persistence.py
│   └── test_insights.py
├── integration/
│   ├── test_pipeline.py
│   └── test_dashboard_data.py
└── fixtures/
    ├── dc_sample.csv
    ├── invalid_duplicate.csv
    └── invalid_ohlc.csv

artifacts/                # Generated locally; not committed
docs/
├── architecture.md
├── data.md
├── domain.md
├── operations.md
└── decisions.md

requirements.txt
requirements-dev.txt
.gitignore
README.md
```

**Structure Decision**: Single-project layout. `btc_forecast` contains pure domain and
application logic; `app.py` and `btc_forecast/dashboard/` contain presentation. `tests/` mirrors
the domain modules and includes deterministic fixtures. Generated models and reports live under
`artifacts/` and are excluded from version control.

## Implementation Approach

1. **Foundation**: Create the virtual environment, pinned requirements, data loader, validation,
   preprocessing summary and deterministic test fixtures.
2. **Model and evaluation**: Implement the training-only ARIMA order search, naive baseline,
   one-step-ahead validation walk-forward and metric calculations.
3. **Persistence and CLI**: Implement the versioned artifact contract, production refit on all
   records, pickle round-trip, `train` and `predict` commands, and error handling.
4. **Dashboard**: Build the Streamlit entry point, artifact loading and caching, live next-day
   inference, historical/forecast chart, validation backtest chart, metrics table, insights and
   empty/error states.
5. **Documentation and gates**: Update `README.md`, add the project documents, run Ruff, pytest,
   compile checks and the quickstart scenarios.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations. The project remains a single application with no additional services or
infrastructure.
