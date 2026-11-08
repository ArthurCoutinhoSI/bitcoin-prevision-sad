# Bitcoin Next-Day Forecast (Decision Support)

A local, single-user decision-support application for Bitcoin's next-day USD closing price. It
trains one ARIMA model on `dc.csv`, evaluates it against a naive last-value baseline on an
untouched chronological validation period, persists the fitted model, and presents the forecast,
metrics and data-quality insights on a local Streamlit dashboard.

This project does **not** recommend buying, selling or holding Bitcoin, does not provide price
targets or trading signals, and does not execute trades. Forecasts are estimates and are not
financial advice.

## Scope

In scope:

- CSV loading, validation, cleaning and fingerprinting of the local dataset.
- One non-seasonal ARIMA model using the USD closing price only.
- One naive last-value baseline for comparison.
- An 80/20 chronological split; configuration selection uses only the training period.
- One-step-ahead walk-forward evaluation with MAE, MSE, RMSE and R².
- Pickle-persisted model plus JSON and CSV evaluation artifacts.
- A read-only Streamlit dashboard with two interactive Altair charts, metrics, insights,
  limitations and a disclaimer.

Out of scope: live market feeds, external APIs, databases, authentication, cloud deployment,
multi-user sessions, trade execution, additional datasets, extra forecast horizons, portfolio
tracking and buy/sell/hold recommendations.

## Quick start

From the repository root:

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# If `python3 -m venv` fails because ensurepip is unavailable, use uv:
# uv venv .venv --python 3.13 && source .venv/bin/activate
# uv pip install -r requirements.txt -r requirements-dev.txt

# 2. Install pinned dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-dev.txt

# 3. Train, evaluate and persist the model
python -m btc_forecast.cli train --data dc.csv --artifacts artifacts

# 4. Generate the next-day forecast without retraining
python -m btc_forecast.cli predict --artifacts artifacts

# 5. Launch the dashboard
streamlit run app.py
```

Open the URL Streamlit prints, normally <http://localhost:8501>. The dashboard never trains a
model; it reads `artifacts/` and refuses to display a forecast when the artifacts are missing,
corrupt or built from a different dataset.

## Commands

| Command | Purpose |
|---------|---------|
| `python -m btc_forecast.cli train --data dc.csv --artifacts artifacts` | Validate, clean, split, select ARIMA order, evaluate, refit and write artifacts |
| `python -m btc_forecast.cli predict --artifacts artifacts` | Load the persisted model and print the next-day forecast |
| `python -m btc_forecast.cli predict --artifacts artifacts --json` | Same forecast as machine-readable JSON |
| `streamlit run app.py` | Launch the local read-only dashboard |
| `python -m pytest` | Run unit and integration tests |
| `ruff check .` | Lint |
| `ruff format --check .` | Verify formatting |
| `python -m compileall -q btc_forecast app.py` | Syntax/build check |

CLI exit codes: `0` success, `1` unexpected failure, `2` invalid data or arguments, `3` no ARIMA
candidate fitted, `4` artifact failure.

## Artifacts

Training writes three files under `artifacts/` (excluded from version control):

| File | Format | Contents |
|------|--------|----------|
| `model.pkl` | Pickle | Production ARIMA result, order, date ranges, preprocessing summary, evaluation report, dataset fingerprint |
| `evaluation.json` | JSON | Split, selected configuration, ARIMA and baseline metrics, baseline comparison, limitations |
| `validation_predictions.csv` | CSV | Validation dates, actual closes, ARIMA predictions and baseline predictions |

Only load a `model.pkl` produced by this project. Pickle can execute code during load.

## Reference result for the provided dataset

The committed `dc.csv` contains 1000 records from `2018-05-07` to `2021-01-30`. A reference run
selects ARIMA(1, 1, 0) by AIC and produces:

| Model | MAE | MSE | RMSE | R² |
|-------|-----|-----|------|----|
| ARIMA | 499.458430 | 756897.792690 | 869.998731 | 0.989742 |
| Naive Last Value | 494.089150 | 734652.787410 | 857.118888 | 0.990043 |

The naive baseline has the lower validation RMSE in this run. The report states that result
honestly; no minimum accuracy threshold is imposed. The production refit forecasts
`2021-01-31` at approximately `USD 34,217.46`.

## Project layout

```text
app.py                    Streamlit entry point (presentation only)
btc_forecast/
├── config.py             Constants, paths, grid, artifact version
├── data.py               CSV loading, schema validation, fingerprint
├── preprocessing.py      Ordering, duplicates, forward fill, OHLC checks
├── model.py              ARIMA selection, fitting, walk-forward, inference
├── evaluation.py         Baseline, metrics, evaluation report
├── persistence.py        Atomic artifact writes and validated loading
├── insights.py           Direction, percentage change, comparison, limitations
├── pipeline.py           End-to-end training orchestration
├── cli.py                train and predict commands
└── dashboard/data.py     Dashboard view assembly (no Streamlit imports)
tests/
├── unit/                 Module-level tests with deterministic fixtures
├── integration/          Pipeline, CLI and dashboard-data tests
└── fixtures/             Small deterministic CSV fixtures
docs/                     Architecture, data, domain, operations and decisions
artifacts/                Generated locally; ignored by git
```

## Documentation

- [Architecture](docs/architecture.md) — layer boundaries and module responsibilities.
- [Data](docs/data.md) — `dc.csv` schema, cleaning rules, fingerprinting and limitations.
- [Domain](docs/domain.md) — forecast target, split, ARIMA selection, evaluation and metrics.
- [Operations](docs/operations.md) — setup, commands, exit codes, dashboard states and measured
  performance.
- [Decisions](docs/decisions.md) — significant technical decisions and rejected alternatives.

Feature-level design records live in
[`specs/001-bitcoin-forecast-dashboard/`](specs/001-bitcoin-forecast-dashboard/).

## Limitations

- Univariate ARIMA uses only the USD closing price; it does not use volume, on-chain data, news or
  macro indicators.
- The dataset ends on `2021-01-30`; forecasts are only for the next day relative to that series.
- One-step-ahead validation metrics do not guarantee future accuracy.
- Cryptocurrency prices are volatile; historical fit and short-horizon accuracy can deteriorate
  quickly.
- The dashboard is a local, single-user tool with no authentication and no live data.

Forecasts are estimates, are not guarantees and do not constitute financial advice.
