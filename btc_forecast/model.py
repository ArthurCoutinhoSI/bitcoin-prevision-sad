"""ARIMA order selection, fitting and one-step-ahead walk-forward evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC

import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA, ARIMAResults

from btc_forecast.config import (
    ARIMA_ORDER_GRID,
    DATE_COLUMN,
    TARGET_COLUMN,
    TRAIN_RATIO,
)


class ModelError(RuntimeError):
    """Raised when the series cannot be split or no ARIMA candidate fits."""


@dataclass(frozen=True)
class ChronologicalSplit:
    """A chronological training / validation split."""

    train: pd.Series
    validation: pd.Series
    train_range: tuple[str, str]
    validation_range: tuple[str, str]
    split_method: str = "chronological"

    @property
    def train_count(self) -> int:
        return len(self.train)

    @property
    def validation_count(self) -> int:
        return len(self.validation)

    def to_dict(self) -> dict[str, object]:
        return {
            "train_range": list(self.train_range),
            "validation_range": list(self.validation_range),
            "train_count": self.train_count,
            "validation_count": self.validation_count,
            "split_method": self.split_method,
        }


@dataclass(frozen=True)
class ARIMAConfiguration:
    """Selected ARIMA order and the evidence used to select it."""

    order: tuple[int, int, int]
    aic: float
    fitted_on: tuple[str, str]
    name: str = "ARIMA"
    selection_method: str = "AIC"
    candidate_grid: dict[str, list[int]] = field(
        default_factory=lambda: {
            key: list(values) for key, values in ARIMA_ORDER_GRID.items()
        }
    )

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "order": list(self.order),
            "selection_method": self.selection_method,
            "candidate_grid": {
                key: list(values) for key, values in self.candidate_grid.items()
            },
            "aic": self.aic,
            "fitted_on": list(self.fitted_on),
        }


def series_from_records(records: pd.DataFrame) -> pd.Series:
    """Build the univariate close series with a chronological date index."""

    ordered = records.sort_values(DATE_COLUMN, kind="mergesort")
    values = ordered[TARGET_COLUMN].astype(float).to_numpy()
    index = pd.DatetimeIndex(ordered[DATE_COLUMN])
    return pd.Series(values, index=index, name=TARGET_COLUMN)


def _range(series: pd.Series) -> tuple[str, str]:
    return (
        series.index.min().date().isoformat(),
        series.index.max().date().isoformat(),
    )


def split_chronological(
    records: pd.DataFrame, train_ratio: float = TRAIN_RATIO
) -> ChronologicalSplit:
    """Split records into the first ``train_ratio`` and the remaining validation set."""

    series = series_from_records(records)
    count = len(series)
    if count < 5:
        raise ModelError(
            "At least 5 chronological observations are required to train and evaluate; "
            f"found {count}."
        )

    split_index = int(count * train_ratio)
    if split_index < 2 or count - split_index < 1:
        raise ModelError(
            "The requested split leaves too few training or validation observations."
        )

    train = series.iloc[:split_index]
    validation = series.iloc[split_index:]
    return ChronologicalSplit(
        train=train,
        validation=validation,
        train_range=_range(train),
        validation_range=_range(validation),
    )


def fit_arima(series: pd.Series, order: tuple[int, int, int]) -> ARIMAResults:
    """Fit a non-seasonal ARIMA model with the given order."""

    values = np.asarray(series, dtype=float)
    if len(values) < 3:
        raise ModelError("At least 3 observations are required to fit ARIMA.")
    if not np.isfinite(values).all():
        raise ModelError("ARIMA input contains missing or non-finite values.")

    try:
        return ARIMA(values, order=order).fit()
    except Exception as exc:  # statsmodels raises several error types
        raise ModelError(f"ARIMA{order} could not be fitted: {exc}") from exc


def select_arima_order(
    train_series: pd.Series,
    grid: dict[str, tuple[int, ...] | list[int]] = ARIMA_ORDER_GRID,
) -> ARIMAConfiguration:
    """Search a fixed grid on training data only and return the lowest-AIC order."""

    best_order: tuple[int, int, int] | None = None
    best_aic = float("inf")
    last_error: Exception | None = None

    for p in grid["p"]:
        for d in grid["d"]:
            for q in grid["q"]:
                try:
                    fitted = fit_arima(train_series, (p, d, q))
                    aic = float(fitted.aic)
                except ModelError as exc:
                    last_error = exc
                    continue
                if np.isfinite(aic) and aic < best_aic:
                    best_aic = aic
                    best_order = (p, d, q)

    if best_order is None:
        detail = f" Last error: {last_error}" if last_error else ""
        raise ModelError(
            "No ARIMA candidate could be fitted on the training period." + detail
        )

    return ARIMAConfiguration(
        order=best_order,
        aic=best_aic,
        fitted_on=_range(train_series),
        candidate_grid={key: list(values) for key, values in grid.items()},
    )


def walk_forward_predictions(
    split: ChronologicalSplit, order: tuple[int, int, int]
) -> np.ndarray:
    """One-step-ahead validation predictions using only prior actual observations."""

    fitted = fit_arima(split.train, order)
    predictions: list[float] = []
    current = fitted

    for actual in split.validation.to_numpy(dtype=float):
        forecast = current.get_forecast(steps=1).predicted_mean
        value = float(np.asarray(forecast, dtype=float).reshape(-1)[0])
        predictions.append(value)
        try:
            current = current.append([actual], refit=False)
        except Exception as exc:
            raise ModelError(
                "One-step-ahead walk-forward update failed: " + str(exc)
            ) from exc

    result = np.asarray(predictions, dtype=float)
    if not np.isfinite(result).all():
        raise ModelError("Walk-forward evaluation produced a non-finite prediction.")
    return result


def refit_production(series: pd.Series, order: tuple[int, int, int]) -> ARIMAResults:
    """Refit the selected order on the full series for production inference."""

    return fit_arima(series, order)


def forecast_next_day(artifact: dict[str, object]) -> dict[str, object]:
    """Generate one next-day forecast from a validated model artifact."""

    from datetime import datetime

    model = artifact["model"]
    try:
        predicted = model.get_forecast(steps=1).predicted_mean  # type: ignore[attr-defined]
        value = float(np.asarray(predicted, dtype=float).reshape(-1)[0])
        endog = np.asarray(model.model.endog, dtype=float).reshape(-1)  # type: ignore[attr-defined]
    except Exception as exc:
        raise ModelError(
            "Artifact model could not generate a forecast: " + str(exc)
        ) from exc

    if not np.isfinite(value):
        raise ModelError("Artifact model produced a non-finite next-day forecast.")
    if endog.size == 0 or not np.isfinite(endog[-1]):
        raise ModelError(
            "Artifact model does not contain a finite last observed close."
        )

    return {
        "target_date": str(artifact["next_forecast_date"]),
        "predicted_close": value,
        "last_observed_close": float(endog[-1]),
        "model_name": str(artifact.get("model_name", "ARIMA")),
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
