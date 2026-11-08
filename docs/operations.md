# Operations

All commands run from the repository root. After dependency installation, no command requires
network access.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-dev.txt
```

If `python3 -m venv` fails with `ensurepip is not available`, install the OS venv package or use
`uv`:

```bash
uv venv .venv --python 3.13
source .venv/bin/activate
uv pip install -r requirements.txt -r requirements-dev.txt
```

Pinned runtime dependencies: numpy 2.5.4, pandas 3.1.1, statsmodels 0.15.0, streamlit 1.67.0,
altair 6.3.0. Development: pytest 9.2.0, Ruff 0.17.4. Python 3.11+ is required; the reference
environment is Python 3.13.5.

## Training

```bash
python -m btc_forecast.cli train --data dc.csv --artifacts artifacts
```

The command validates and cleans the data, splits 80/20 chronologically, selects the ARIMA order on
training data by AIC, evaluates one-step-ahead ARIMA and naive predictions on validation, computes
MAE/MSE/RMSE/R², refits on all records and writes:

- `artifacts/model.pkl`
- `artifacts/evaluation.json`
- `artifacts/validation_predictions.csv`

It prints record counts, date ranges, the split, the selected order and AIC, both metric rows,
whether ARIMA beat the baseline on RMSE, and artifact paths. Training fails before writing if the
data is invalid or no candidate fits.

## Prediction

```bash
python -m btc_forecast.cli predict --artifacts artifacts
python -m btc_forecast.cli predict --artifacts artifacts --json
```

`predict` reads `dc.csv` only to compute the expected fingerprint; it never fits a model. It loads
and validates `model.pkl`, generates one next-day forecast and prints either a readable summary or a
JSON object with `target_date`, `predicted_close`, `last_observed_close`, `direction`,
`percentage_change`, `model_name` and `generated_at`.

## Dashboard

```bash
streamlit run app.py
```

Open <http://localhost:8501>. The page is read-only. It caches the cleaned dataset with
`st.cache_data` and the loaded model with `st.cache_resource`. The `Reload data` button clears both
caches and reruns the page without retraining.

Sections, top to bottom: header with target, horizon, model order, data range, last observed date,
artifact timestamp, fingerprint and version; forecast summary; historical/forecast chart; validation
metrics; validation backtest chart; insights; footer with the reproduction command and disclaimer.

Charts support hover, zoom and pan through Altair. The forecast is a distinct diamond marker with a
dashed rule and a text label; no line is interpolated to it.

### Dashboard states

| State | Trigger | Behavior |
|-------|---------|----------|
| `ready` | Valid artifact and matching fingerprint | All sections render |
| `partial_artifacts` | Valid model but `evaluation.json` or `validation_predictions.csv` missing/unreadable | Forecast and metrics from the artifact; info message for the missing section |
| `missing_artifacts` | `artifacts/model.pkl` absent | Empty state names the file and shows the training command; no forecast or metrics |
| `invalid_artifacts` | Corrupt file, wrong version, missing key, fingerprint mismatch or non-finite forecast | Specific plain-language reason and remediation; no forecast or metrics |
| `data_error` | `dc.csv` missing or unreadable | Actionable data error naming the file; no forecast |

Failure states never display fabricated prices, zero-filled metrics or stale forecasts.

## Exit codes

| Code | Meaning | First action |
|------|---------|--------------|
| 0 | Success | Continue |
| 1 | Unexpected failure | Re-run with the error visible |
| 2 | Invalid data or arguments | Check `dc.csv` and command options |
| 3 | No ARIMA candidate fitted | Inspect the data range and value distribution |
| 4 | Artifact write, load or verification failure | Check permissions, version and fingerprint |

## Artifact regeneration

Delete and regenerate at any time:

```bash
rm -rf artifacts
python -m btc_forecast.cli train --data dc.csv --artifacts artifacts
```

Artifacts are ignored by git; each clone must train once before using the dashboard or `predict`.

## Fingerprint mismatch recovery

A mismatch means `dc.csv` changed after training. The dashboard refuses to forecast from the stale
artifact. Re-run training so all three artifacts are rebuilt from the current file, then press
`Reload data`.

## Pickle trust restriction

`model.pkl` is a Python pickle and can execute code during load. Only load artifacts produced by
this project. Do not copy artifacts from untrusted sources and do not expose the artifact directory
to untrusted writes.

## Quality gates

```bash
python -m pytest
ruff check .
ruff format --check .
python -m compileall -q btc_forecast app.py
```

All four must pass. `ruff format --check` reports drift; `ruff format .` fixes it.

## Measured performance

Measured on the reference environment (Linux, Python 3.13.5, 1000 records) with
`PYTHONPATH=. .venv/bin/python`:

| Operation | Measured | Criterion |
|-----------|----------|-----------|
| Full training, evaluation and persistence | 6.65 s | ≤ 300 s |
| Model artifact load (median of 5) | 0.0041 s | ≤ 1 s |
| Next-day inference after load (median of 200) | 1.09 ms | ≤ 100 ms |
| Dashboard data assembly (median of 5) | 0.028 s | — |
| Streamlit first render via `AppTest` (cold) | 2.45 s | ≤ 5 s |

All criteria are met, with ample margin. Times vary with hardware but the workload is small
(1000 daily records).

## Troubleshooting

| Symptom | Likely cause | Remedy |
|---------|--------------|--------|
| `ModuleNotFoundError: btc_forecast` | Not run from the repository root | `cd` to the repository root |
| `ModuleNotFoundError: statsmodels` | Dependencies installed outside the active environment | Activate `.venv` and reinstall |
| Dashboard shows `missing_artifacts` | Training has not run or wrote elsewhere | Run training with `--artifacts artifacts` |
| Dashboard shows `invalid_artifacts` | Corrupt artifact, wrong version or fingerprint mismatch | Re-run training; then `Reload data` |
| Port 8501 in use | Another Streamlit process is running | `streamlit run app.py --server.port 8502` |
| `ruff` or `pytest` not found | Development dependencies not installed | Install `requirements-dev.txt` |
