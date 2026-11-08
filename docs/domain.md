# Domain Rules

## Forecast target and horizon

- Target: the USD closing price (`close_USD`) of the day immediately after the last observed date.
- Horizon: exactly one day. For the provided dataset, the last observation is `2021-01-30`, so the
  forecast target is `2021-01-31`.
- Input: the univariate historical `close_USD` series only.
- Model: exactly one non-seasonal ARIMA configuration, selected from a fixed grid.
- Baseline: a naive last-value predictor that repeats the previous actual close.

Multi-day horizons, intraday values, volume forecasting and additional model families are out of
scope.

## Chronological split

The cleaned series is split by position, never shuffled:

- First 80% → training period (800 records for the provided dataset).
- Final 20% → validation period (200 records, `2020-07-15` to `2021-01-30`).

The validation period is the untouched final evaluation set. It is not used for ARIMA order
selection, scaling or any other configuration choice. There is no separate test set.

## ARIMA order selection

A fixed grid is searched on the training series only:

- `p` (autoregressive) ∈ {0, 1, 2}
- `d` (differencing) ∈ {0, 1}
- `q` (moving average) ∈ {0, 1, 2}

Each candidate is fitted with `statsmodels.tsa.arima.model.ARIMA`; the candidate with the lowest
finite AIC wins. If no candidate fits, the run fails with an actionable error rather than falling
back silently. The selected order is recorded with its AIC, candidate grid and training range.

For the provided dataset the selected order is ARIMA(1, 1, 0) with AIC 11380.030974.

## Production refit

After evaluation, the selected order is refit on all 1000 records to produce the model used for
next-day inference. This is required because the evaluation model sees only the first 800 records;
using it for production would require a 200-step-ahead forecast rather than a genuine next-day
forecast. The reported metrics remain out-of-sample from the evaluation model and are not
recomputed after the refit.

## One-step-ahead walk-forward evaluation

For each validation day in order:

1. Predict the next close using only observations available up to the previous day.
2. Record the prediction.
3. Append the actual close to the model state without refitting.
4. Move to the next validation day.

The first prediction is made from the fitted training model. Actual validation values are used
only after each prediction has been recorded, so no future information leaks backwards. The
walk-forward procedure measures next-day accuracy, not recursive multi-step accuracy.

The naive baseline follows the same one-step-ahead rule: prediction for day *t* equals the actual
close on day *t − 1*.

## Metrics

Given actual values `y_i` and predictions `ŷ_i` over `n` validation observations:

| Metric | Formula |
|--------|---------|
| MAE | `mean(|y_i − ŷ_i|)` |
| MSE | `mean((y_i − ŷ_i)²)` |
| RMSE | `sqrt(MSE)` |
| R² | `1 − Σ(y_i − ŷ_i)² / Σ(y_i − ȳ)²` |

R² is reported as `null` (displayed `N/A`) when the validation actuals have zero variance, because
the denominator would be zero. Metrics are computed independently for ARIMA and the baseline over
the same validation observations.

`outperforms_baseline_rmse` is `true` only when the ARIMA validation RMSE is strictly lower than
the baseline RMSE. No minimum accuracy threshold is imposed; reporting that the baseline won is a
valid, honest outcome.

### Reference values

| Model | MAE | MSE | RMSE | R² |
|-------|-----|-----|------|----|
| ARIMA(1, 1, 0) | 499.458430 | 756897.792690 | 869.998731 | 0.989742 |
| Naive Last Value | 494.089150 | 734652.787410 | 857.118888 | 0.990043 |

Baseline lower RMSE: yes. `outperforms_baseline_rmse`: `false`.

## Forecast direction and percentage change

- `percentage_change = (predicted_close − last_observed_close) / last_observed_close`.
- Direction is `up` when the change is positive, `down` when negative and `flat` when exactly zero.
- Non-finite predictions or a non-positive last close are errors; no forecast is produced.

The dashboard formats prices as `USD` with two decimals and thousands separators, and percentages
as signed values with two decimals.

## Interpretation boundary

The system produces a forecast, evaluation metrics and data-quality observations only. It never
outputs buy, sell or hold recommendations, price targets, position sizing or trading signals, and
it does not execute trades. The disclaimer states that forecasts are estimates, are not guarantees
and do not constitute financial advice.

## Determinism

Given the same `dc.csv` and configuration, the split, selected order, predictions and metrics are
reproducible. Repeated training runs on the same machine produce metrics identical within `1e-6`.
The default ARIMA fit is deterministic; the test suite asserts the tolerance explicitly.
