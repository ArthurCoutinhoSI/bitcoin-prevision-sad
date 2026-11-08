# Decisions

Significant technical decisions for this feature. Alternatives are recorded to explain why the
current, smaller design was preferred.

## 1. Python with a repository-local virtual environment

- **Decision**: Python 3.13.5 in `.venv`, with pinned `requirements.txt` and
  `requirements-dev.txt`.
- **Reason**: Requested language; local isolation makes runs reproducible without adding a package
  manager.
- **Rejected**: System-wide installs (version leakage), Conda/Poetry/pipx (extra tooling without a
  requirement). `uv` is documented only as a fallback when `python3 -m venv` lacks `ensurepip`.

## 2. pandas for CSV ingestion

- **Decision**: Load `dc.csv` with pandas, treat the first unnamed column as `date`, parse dates and
  validate types.
- **Reason**: The file is small and local; pandas handles typed columns and date parsing with less
  custom code.
- **Rejected**: Standard-library `csv` (manual type/date handling), Polars (second dataframe
  dependency).

## 3. Deterministic cleaning without scaling

- **Decision**: Sort, remove exact duplicates, fail on conflicting dates, forward-fill missing
  prices, drop rows without a prior close, validate OHLC, and do not scale the series.
- **Reason**: ARIMA models levels and differences; scaling adds inverse-transform complexity and
  potential leakage without changing forecasts materially. Forward fill is deterministic and never
  uses future values.
- **Rejected**: Dropping all rows with missing data (loses information), interpolation (invents
  values), standardization (unnecessary for a univariate ARIMA).

## 4. 80/20 chronological split with one-step walk-forward

- **Decision**: First 80% for training, final 20% for validation; evaluate one step at a time using
  only prior actuals.
- **Reason**: Prevents future leakage and mirrors the next-day use case without compounding
  multi-step error. The validation period stays untouched for final evaluation.
- **Rejected**: Shuffled splits (leakage), recursive multi-step validation (measures a different
  task), rolling retraining (runtime and complexity without a product need).

## 5. ARIMA order selected by AIC on training data only

- **Decision**: `statsmodels` ARIMA with a fixed grid `p` 0–2, `d` 0–1, `q` 0–2; choose the lowest
  finite AIC; fail clearly if no candidate fits.
- **Reason**: Small, deterministic, fast for 800 observations and keeps validation untouched.
- **Rejected**: `pmdarima.auto_arima` (extra dependency), Prophet (heavier, outside the requested
  model), exponential smoothing (ARIMA was requested), hand-written ARIMA (high risk).

## 6. Production refit on all records after evaluation

- **Decision**: Evaluate the 80% model, then refit the selected order on all 1000 records for
  inference. Metrics remain out-of-sample.
- **Reason**: A production forecast for `2021-01-31` must be one step after the last observation,
  not a 200-step forecast from the 80% model. This follows the standard
  train/evaluate/deploy sequence.
- **Rejected**: Keeping the 80% model (not a true next-day forecast), training on all data before
  evaluation (leaks validation), persisting two models (unnecessary).

## 7. Naive last-value baseline

- **Decision**: Predict each validation day with the previous actual close.
- **Reason**: Transparent, parameter-free and aligned with the one-step-ahead task.
- **Rejected**: Moving-average and seasonal-naive baselines (extra parameters without a
  requirement).

## 8. Metrics implemented with numpy

- **Decision**: Explicit MAE, MSE, RMSE and R² formulas; R² is `null` for zero-variance actuals.
- **Reason**: Four formulas do not justify a machine-learning dependency, and explicit code is easy
  to test.
- **Rejected**: scikit-learn (large dependency for four metrics), statsmodels diagnostics (do not
  give the required two-model comparison table).

## 9. Standard-library pickle persistence with atomic writes

- **Decision**: Persist a versioned dictionary containing the fitted production ARIMA result and
  metadata to `model.pkl`; write via a temporary file and atomic rename; validate version, keys,
  types, order, date ranges, target, horizon, fingerprint and a finite one-step forecast on load.
- **Reason**: `pickle` is built in, serializes the statsmodels result, and the artifact stays local.
  Atomic writes prevent partially written files.
- **Rejected**: joblib (extra dependency), JSON (cannot serialize the model), ONNX (unnecessary
  tooling and conversion risk).
- **Security**: Never load a pickle from an untrusted source.

## 10. Streamlit with Altair

- **Decision**: Streamlit dashboard with layered Altair charts; `st.cache_resource` for the model,
  `st.cache_data` for the dataset/report.
- **Reason**: Streamlit is the requested frontend; Altair is already a Streamlit dependency and
  cleanly layers a historical line, forecast marker and baseline series with hover, zoom and pan.
- **Rejected**: Plotly (extra chart dependency), native Streamlit charts (poor layering of the
  forecast point), Flask + JavaScript (much more code).

## 11. Two charts and an insights panel

- **Decision**: Historical close with a labeled forecast marker, plus validation actuals versus
  ARIMA and naive baseline.
- **Reason**: The second chart makes the reported metrics inspectable, directly supporting the
  insights requirement without adding a new feature area.
- **Rejected**: Metrics-only dashboard (hides forecast quality), extra pages/filters/controls (out
  of scope).

## 12. pytest, Ruff and compileall

- **Decision**: pytest for unit/integration tests with deterministic CSV fixtures and temporary
  directories; Ruff for lint and format; `compileall` for syntax verification.
- **Reason**: Meets the constitution's deterministic-test and static-check requirements with one
  test dependency and one lint dependency.
- **Rejected**: `unittest` alone (more boilerplate), multiple lint tools (Ruff covers lint and
  formatting).

## 13. Documentation set

- **Decision**: `README.md` as the entry point plus `docs/architecture.md`, `docs/data.md`,
  `docs/domain.md`, `docs/operations.md` and this decisions file.
- **Reason**: The constitution requires purpose, setup, architecture, domain rules, data provenance,
  contracts, operations and significant decisions to be documented and current.
- **Rejected**: One long README (mixes concerns), code comments only (no operational entry point).

## 14. Honest baseline reporting

- **Decision**: Always state whether ARIMA beat the naive baseline on validation RMSE; do not fail
  the run or hide the result when it does not.
- **Reason**: The specification requires a complete comparison without a minimum-accuracy
  threshold. The reference run honestly reports that the baseline had the lower RMSE.
- **Rejected**: Requiring ARIMA to win (would make a valid run fail), omitting the comparison
  (violates FR-022/SC-009).
