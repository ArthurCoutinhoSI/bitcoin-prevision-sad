# Quickstart: Bitcoin Forecast Dashboard

**Feature**: `001-bitcoin-forecast-dashboard` | **Date**: 2026-11-08

This guide takes a clean machine with Python installed to a running dashboard. All commands run
from the repository root. After dependency installation, nothing in this workflow uses the
network.

## Prerequisites

- Python 3.11 or newer (reference environment: Python 3.13.5).
- `dc.csv` in the repository root.
- Approximately 500 MB of free disk space for the virtual environment and dependencies.
- No database, cloud account, API key or market data subscription is required.

Verify Python:

```bash
python3 --version
```

## 1. Create the virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows PowerShell
python --version
```

If `python3 -m venv` fails with `ensurepip is not available` (common on Debian/Ubuntu without
`python3-venv`), install that OS package with administrator rights, or create the environment with
`uv` and continue using the same activation and commands:

```bash
uv venv .venv --python 3.13
source .venv/bin/activate
uv pip install -r requirements.txt -r requirements-dev.txt
```

The `.venv/` directory is excluded from version control. Do not install project dependencies
system-wide.

## 2. Install pinned dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
```

Pinned runtime versions:

```text
numpy==2.5.4
pandas==3.1.1
statsmodels==0.15.0
streamlit==1.67.0
altair==6.3.0
```

Pinned development versions:

```text
pytest==9.2.0
ruff==0.17.4
```

No other runtime dependency is required. If installation fails, confirm that the Python version
satisfies the minimum for `numpy 2.5.4` (Python 3.12 or newer for the reference versions) and
retry with a supported interpreter.

## 3. Run training and evaluation

```bash
python -m btc_forecast.cli train --data dc.csv --artifacts artifacts
```

This single command:

1. Loads and validates `dc.csv`.
2. Cleans, orders and summarizes the data.
3. Splits into 80% training and 20% validation.
4. Selects the ARIMA order by AIC using only training data.
5. Evaluates one-step-ahead ARIMA and naive baseline predictions on validation.
6. Computes MAE, MSE, RMSE and R² for both.
7. Refits the selected order on all records for production.
8. Writes the artifacts.

Expected output includes the record counts, date ranges, selected order, a metric table and the
artifact paths. For the provided dataset expect:

- 1000 accepted records.
- Date range `2018-05-07` to `2021-01-30`.
- 800 training records (`2018-05-07` to `2020-07-14`) and 200 validation records
  (`2020-07-15` to `2021-01-30`).
- ARIMA(1, 1, 0) selected by AIC.
- Validation RMSE `869.998731` for ARIMA and `857.118888` for the naive baseline, so
  `outperforms_baseline_rmse` is `false`. This is a valid, honestly reported outcome.
- Next forecast date `2021-01-31`.
- `artifacts/model.pkl`, `artifacts/evaluation.json` and
  `artifacts/validation_predictions.csv` created.

Exit codes:

| Code | Meaning | First action |
|------|---------|--------------|
| 0 | Success | Continue |
| 1 | Unexpected failure | Re-run with the traceback visible |
| 2 | Invalid data or arguments | Check `dc.csv` and the command options |
| 3 | No ARIMA candidate fitted | Inspect the data range and value distribution |
| 4 | Artifact write or verification failure | Check directory permissions and free space |

## 4. Generate a forecast without retraining

```bash
python -m btc_forecast.cli predict --artifacts artifacts
```

Machine-readable form:

```bash
python -m btc_forecast.cli predict --artifacts artifacts --json
```

Expected JSON fields: `target_date`, `predicted_close`, `last_observed_close`, `direction`,
`percentage_change`, `model_name`, `generated_at`.

This command must complete within 1 second of model load and must not read `dc.csv` for retraining.
`--data` defaults to `dc.csv` and is used only to verify the artifact fingerprint; point it at the
dataset that produced the artifact if they differ.

Expected reference values: target date `2021-01-31`, predicted close approximately `USD 34,217.46`,
last observed close `USD 34,218.54`, direction `down`.

## 5. Launch the dashboard

```bash
streamlit run app.py
```

Open the URL Streamlit prints, normally `http://localhost:8501`. Verify:

- The header shows the model order, last observed date and the financial-advice disclaimer.
- The next-day forecast for `2021-01-31` is visible with direction and percentage change.
- The historical chart includes the forecast marker.
- The metrics table shows ARIMA and `Naive Last Value` values for MAE, MSE, RMSE and R².
- The validation backtest chart shows actual, ARIMA and baseline series.
- The insights panel shows direction, baseline comparison, data quality and limitations.
- No buy, sell or hold recommendation appears anywhere.

Stop the server with `Ctrl+C`.

## 6. Run the quality gates

```bash
python -m pytest
ruff check .
ruff format --check .
python -m compileall -q btc_forecast app.py
```

All four commands must pass before considering the feature complete. `ruff format --check`
reports formatting drift without modifying files; use `ruff format .` to fix it.

## 7. Validation scenarios

Run these scenarios to confirm the feature against the specification.

| # | Scenario | Steps | Expected result |
|---|----------|-------|-----------------|
| 1 | Happy path | Run training, predict and dashboard | Exit code 0; forecast for `2021-01-31`; all dashboard sections visible |
| 2 | Determinism | Run training twice into two artifact directories | Metrics identical within `1e-6` |
| 3 | Split integrity | Inspect `evaluation.json` | `train_count == 800`, `validation_count == 200`, training range ends before validation starts |
| 4 | Baseline comparison | Inspect `evaluation.json` | `model_metrics` and `baseline_metrics` share `observation_count == 200`; `outperforms_baseline_rmse` is consistent with RMSE |
| 5 | Missing artifact | Move `artifacts/model.pkl` aside and open the dashboard | Actionable empty state; no forecast or metrics; no crash |
| 6 | Corrupt artifact | Replace `model.pkl` with a text file and open the dashboard | Actionable invalid-artifact message; no forecast |
| 7 | Fingerprint mismatch | Modify `dc.csv` and open the dashboard with the old artifact | Stale forecast refused; actionable message |
| 8 | Partial artifacts | Remove `validation_predictions.csv` and open the dashboard | Forecast and metrics still shown; backtest section explains the missing file |
| 9 | Predict without training | Run `predict` in a clean artifact directory | Exit code 4 with an actionable message |
| 10 | Invalid OHLC | Run training against `tests/fixtures/invalid_ohlc.csv` | Exit code 2 with the violating record identified |
| 11 | Conflicting duplicate dates | Run training against `tests/fixtures/invalid_duplicate.csv` | Exit code 2; conflicting date reported |
| 12 | Disclaimer | Search the rendered dashboard | Disclaimer visible together with the forecast; no recommendation language |
| 13 | Offline operation | Disable network after installation and repeat scenarios 1, 4 and 5 | All succeed; no network calls |
| 14 | Performance | Time training and dashboard first render | Training at most 5 minutes; model load at most 1 second; inference at most 100 ms; dashboard first content at most 5 seconds in the reference environment. See `docs/operations.md` for measured values |

## 8. Cleanup and regeneration

Regenerate all artifacts at any time by deleting the directory and re-running training:

```bash
rm -rf artifacts
python -m btc_forecast.cli train --data dc.csv --artifacts artifacts
```

Artifacts are not committed. Never load a `model.pkl` from an untrusted source: pickle can
execute code during load. Delete `.venv/` and `artifacts/` before archiving the repository if a
clean copy is required.

## Troubleshooting

| Symptom | Likely cause | Remedy |
|---------|--------------|--------|
| `ModuleNotFoundError: btc_forecast` | Not run from the repository root or the package is missing | `cd` to the repository root and confirm the `btc_forecast/` package exists |
| `ModuleNotFoundError: statsmodels` | Dependencies installed outside the active environment | Activate `.venv` and reinstall `requirements.txt` |
| Dashboard shows the empty state | Training has not run or wrote to another directory | Run the training command with `--artifacts artifacts` |
| Dashboard shows a fingerprint mismatch | `dc.csv` changed after training | Re-run training to regenerate artifacts |
| Port 8501 already in use | Another Streamlit process is running | `streamlit run app.py --server.port 8502` |
| `ruff` or `pytest` not found | Development requirements not installed | `python -m pip install -r requirements-dev.txt` |

## Reference Environment

Timing criteria assume a machine with at least 4 GB of RAM and 2 CPU cores running the documented
setup. Results may be slower on constrained hardware but must remain functionally identical.
