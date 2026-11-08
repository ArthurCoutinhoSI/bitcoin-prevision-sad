# CLI Contract

**Feature**: `001-bitcoin-forecast-dashboard` | **Version**: 1 | **Date**: 2026-11-08

The CLI is local and offline. It does not expose a network service and does not require
authentication.

## `train`

Runs validation, preprocessing, ARIMA order selection, validation evaluation, baseline
comparison, production refit and artifact persistence.

```text
python -m btc_forecast.cli train [--data PATH] [--artifacts DIR]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--data` | `dc.csv` | Path to the source CSV |
| `--artifacts` | `artifacts` | Directory for generated artifacts |

**Inputs**: `dc.csv` with the schema documented in `data-model.md`.

**Behavior**:

1. Load and validate the CSV.
2. Clean and sort the records, then produce the preprocessing summary.
3. Split chronologically into 80% training and 20% validation.
4. Select the ARIMA order by AIC on training data only.
5. Evaluate one-step-ahead ARIMA and naive baseline predictions on validation.
6. Compute MAE, MSE, RMSE and R² for both.
7. Refit the selected order on all accepted records.
8. Persist `model.pkl`, `evaluation.json` and `validation_predictions.csv`.

**Outputs**:

- Human-readable summary on stdout with record counts, date ranges, selected order, metric table
  and artifact paths.
- `artifacts/model.pkl`
- `artifacts/evaluation.json`
- `artifacts/validation_predictions.csv`

**Exit codes**:

| Code | Meaning |
|------|---------|
| 0 | Training, evaluation and persistence succeeded |
| 1 | Unexpected failure |
| 2 | Invalid input data or arguments |
| 3 | No ARIMA candidate could be fitted |
| 4 | Artifact write or verification failure |

**Determinism**: The same input file, configuration and dependency versions produce metrics
identical within `1e-6`.

## `predict`

Loads a persisted production model and generates the next-day forecast without retraining.

```text
python -m btc_forecast.cli predict [--artifacts DIR] [--data PATH] [--json]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--artifacts` | `artifacts` | Directory containing `model.pkl` |
| `--data` | `dc.csv` | Source CSV used only to verify the artifact fingerprint |
| `--json` | off | Print machine-readable JSON instead of a human-readable summary |

**Behavior**:

1. Load `model.pkl`.
2. Validate the artifact version, required keys and dataset fingerprint.
3. Generate one next-day forecast.
4. Print the target date, predicted close, last observed close, direction and percentage change.

**JSON output fields**: `target_date`, `predicted_close`, `last_observed_close`, `direction`,
`percentage_change`, `model_name`, `generated_at`.

**Exit codes**:

| Code | Meaning |
|------|---------|
| 0 | Forecast generated |
| 1 | Unexpected failure |
| 4 | Artifact missing, corrupt, incompatible or fingerprint mismatch |

## `dashboard`

```text
streamlit run app.py
```

**Inputs**: `dc.csv` and the artifacts produced by `train`.

**Behavior**: Starts a local Streamlit server on the default Streamlit port and serves the
dashboard described in `dashboard.md`. It never trains or refits a model.

## Global Rules

- Commands must not access the network.
- Commands must not write outside the selected artifact directory and standard temporary files.
- Secrets and credentials are never accepted or printed.
- The CLI must not emit buy, sell or hold recommendations.
