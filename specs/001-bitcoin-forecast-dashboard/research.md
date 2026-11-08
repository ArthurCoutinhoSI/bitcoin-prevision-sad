# Research: Bitcoin Forecast Dashboard

**Feature**: `001-bitcoin-forecast-dashboard` | **Date**: 2026-11-08

## Decision 1: Python runtime and local dependency isolation

- **Decision**: Use Python 3.13.5 locally with a repository-local virtual environment and pinned
  `requirements.txt` / `requirements-dev.txt` files.
- **Rationale**: Python is the requested language; a virtual environment isolates dependencies and
  makes the setup reproducible without a package manager beyond `pip`.
- **Alternatives considered**: System-wide Python was rejected because dependency versions would
  leak between projects. Conda, Poetry and uv were rejected because they add tooling and
  infrastructure without a concrete requirement.

## Decision 2: CSV ingestion with pandas

- **Decision**: Load `dc.csv` with pandas, treating the first unnamed column as the date, parsing
  dates, sorting ascending, and validating the required `close_USD` field.
- **Rationale**: `dc.csv` is small (1000 rows), already local and read-only. pandas handles typed
  columns, date parsing and ordering with less custom code than the standard-library `csv` module.
- **Alternatives considered**: Standard-library `csv` was rejected due to manual type conversion
  and date handling. Polars was rejected as an unnecessary second dataframe dependency.

## Decision 3: Deterministic cleaning without scaling

- **Decision**: Remove exact duplicate rows, fail on conflicting duplicate dates, forward-fill
  missing price values, exclude rows without a prior valid close, validate OHLC consistency, and
  do not apply normalization or standardization to the ARIMA input.
- **Rationale**: ARIMA models the level and differences of the series; scaling does not change
  forecasts materially and would add inverse-transform complexity. All learned preprocessing is
  avoided, which eliminates training/validation leakage from scaling.
- **Alternatives considered**: Row dropping was rejected because it loses information and makes
  the resulting series irregular. Interpolation was rejected because it introduces invented
  values. Standardization was rejected as unnecessary for a univariate ARIMA model.

## Decision 4: 80/20 chronological split and one-step walk-forward

- **Decision**: Split the sorted series into the first 80% for training and the final 20% for
  validation. The validation period is the untouched final evaluation set. Evaluate with
  one-step-ahead predictions, using only actual observations available before each forecast day.
- **Rationale**: A chronological split prevents future leakage. One-step-ahead evaluation mirrors
  the next-day use case and avoids compounding recursive forecast error.
- **Alternatives considered**: The earlier 80/10/10 split was replaced at user request. Recursive
  multi-step validation was rejected because it measures a different task. Rolling retraining was
  rejected because it adds runtime and complexity without changing the next-day product use case.

## Decision 5: ARIMA selected by AIC on training data only

- **Decision**: Use `statsmodels.tsa.arima.model.ARIMA`. Search a small deterministic grid
  (`p` in 0–2, `d` in 0–1, `q` in 0–2) on the training period and select the lowest AIC. If no
  candidate fits, fail with an actionable error instead of silently falling back.
- **Rationale**: A small grid keeps the search local, reproducible and fast for 800 observations.
  AIC is computed on training data only, so the validation period remains untouched.
- **Alternatives considered**: `pmdarima.auto_arima` was rejected as an additional dependency.
  Prophet was rejected as a heavier dependency outside the requested model. Exponential smoothing
  was considered but ARIMA is the requested model. A hand-written ARIMA implementation was
  rejected as high-risk and unnecessary.

## Decision 6: Production refit after evaluation

- **Decision**: Evaluate the model fitted on the 80% training period. After the evaluation
  completes, refit the selected ARIMA order on all 1000 records to create the production model
  used for next-day inference. Metrics remain out-of-sample from the evaluation model.
- **Rationale**: The dashboard must forecast the day after 2021-01-30. Using the 80% model would
  require a 200-step-ahead forecast, which is not next-day inference. Refitting after evaluation
  is the standard train/evaluate/deploy sequence and does not change the reported metrics.
- **Alternatives considered**: Keeping the 80% model for production was rejected because it does
  not produce a genuine next-day forecast. Training on all records before evaluation was rejected
  because it would leak validation data into the metrics. Persisting two model objects was
  rejected because only the production model is needed for inference.

## Decision 7: Naive last-value baseline

- **Decision**: Compare ARIMA with a naive baseline that predicts the previous actual close for
  each validation day.
- **Rationale**: The baseline is simple, transparent and aligned with the one-step-ahead
  evaluation. It gives the metrics a meaningful reference.
- **Alternatives considered**: Moving-average baselines and seasonal naive baselines were rejected
  because they add parameters or assumptions without being required by the specification.

## Decision 8: Metrics implemented with numpy

- **Decision**: Compute MAE, MSE, RMSE and R² with explicit numpy formulas. Report R² as null when
  the validation actuals have zero variance.
- **Rationale**: Four formulas do not justify a machine-learning dependency. Explicit formulas are
  easy to test and document.
- **Alternatives considered**: scikit-learn was rejected because it adds a large dependency for
  four metrics. statsmodels diagnostics were rejected because they do not directly provide the
  required comparison table for both models.

## Decision 9: Standard-library pickle persistence

- **Decision**: Persist a versioned dictionary containing the fitted production ARIMA result and
  metadata to `artifacts/model.pkl` using the standard-library `pickle` module and an atomic
  write. Validate the artifact version and required keys before use.
- **Rationale**: `pickle` is built into Python, handles the statsmodels result object and requires
  no additional dependency. The artifact is generated and consumed locally.
- **Alternatives considered**: `joblib` was rejected as an extra dependency. JSON was rejected
  because it cannot serialize the fitted model. ONNX was rejected as unnecessary tooling and a
  possible conversion risk.
- **Security note**: Only artifacts generated by this project are loaded. Users must not load
  untrusted pickle files.

## Decision 10: Streamlit with Altair charts

- **Decision**: Use Streamlit for the local dashboard and Altair for a layered historical line,
  forecast point and validation backtest chart. Cache the loaded model with
  `st.cache_resource` and data/reports with `st.cache_data`.
- **Rationale**: Streamlit is the requested frontend and provides rapid local delivery. Altair is
  already a Streamlit dependency and supports hover, zoom and layered marks that native Streamlit
  charts handle poorly for a single forecast point.
- **Alternatives considered**: Plotly was rejected as another charting dependency. Streamlit
  native charts were rejected for the layered forecast marker. Flask plus a JavaScript frontend
  was rejected as significantly more code and dependencies. A notebook was rejected because it is
  not a dashboard.

## Decision 11: Prediction and validation visualization

- **Decision**: The dashboard shows two charts: historical closing price with the next-day forecast
  marker, and validation actuals versus ARIMA and baseline predictions. It also shows metric cards,
  an evaluation table, data-quality insights, limitations and a disclaimer.
- **Rationale**: The second chart makes the reported metrics inspectable and directly supports the
  insights requirement without adding a new feature area.
- **Alternatives considered**: A metrics-only dashboard was rejected because it hides forecast
  quality. Additional pages, filters or user controls were rejected as out of scope.

## Decision 12: Testing and static checks

- **Decision**: Use pytest for unit and integration tests, Ruff for lint and formatting, and
  `python -m compileall` for syntax/build verification. Tests use deterministic CSV fixtures and
  temporary artifact directories and never access the network.
- **Rationale**: The constitution requires deterministic tests and passing static checks. These
  tools cover the requirement with one test dependency and one lint dependency.
- **Alternatives considered**: `unittest` alone was rejected because fixtures and temporary
  directories require more boilerplate. Multiple lint tools were rejected in favor of Ruff.

## Decision 13: Documentation set

- **Decision**: Maintain `README.md` as the entry point and add `docs/architecture.md`,
  `docs/data.md`, `docs/domain.md`, `docs/operations.md` and `docs/decisions.md`.
- **Rationale**: The constitution requires purpose, setup, architecture, domain rules and
  assumptions, data provenance and limitations, public contracts, operations and significant
  decisions to be documented.
- **Alternatives considered**: A single long README was rejected because it would mix setup,
  architecture, domain rules and troubleshooting. Code comments alone were rejected because they
  do not provide an operational entry point.

## Open Questions

None. All technical unknowns are resolved. The implementation phase may record the exact ARIMA
order and metric values produced by the final run in the project documentation.
