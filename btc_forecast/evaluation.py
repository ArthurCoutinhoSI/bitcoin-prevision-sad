"""Naive baseline, metric calculations and evaluation report construction."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from btc_forecast.model import ARIMAConfiguration, ChronologicalSplit
from btc_forecast.preprocessing import PreprocessingSummary


@dataclass(frozen=True)
class EvaluationMetrics:
    """Metrics over one set of one-step-ahead predictions."""

    mae: float
    mse: float
    rmse: float
    r2: float | None
    observation_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "mae": self.mae,
            "mse": self.mse,
            "rmse": self.rmse,
            "r2": self.r2,
            "observation_count": self.observation_count,
        }


@dataclass(frozen=True)
class EvaluationReport:
    """Out-of-sample evaluation of the model and the naive baseline."""

    generated_at: str
    dataset_fingerprint: str
    split: ChronologicalSplit
    model: ARIMAConfiguration
    model_metrics: EvaluationMetrics
    baseline_metrics: EvaluationMetrics
    outperforms_baseline_rmse: bool
    preprocessing: PreprocessingSummary
    limitations: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at,
            "dataset_fingerprint": self.dataset_fingerprint,
            "split": self.split.to_dict(),
            "model": self.model.to_dict(),
            "model_metrics": self.model_metrics.to_dict(),
            "baseline_metrics": self.baseline_metrics.to_dict(),
            "outperforms_baseline_rmse": self.outperforms_baseline_rmse,
            "preprocessing": self.preprocessing.to_dict(),
            "limitations": list(self.limitations),
        }


def baseline_predictions(
    train_series: pd.Series, validation_series: pd.Series
) -> np.ndarray:
    """Predict each validation day with the previous actual closing price."""

    if len(train_series) == 0 or len(validation_series) == 0:
        raise ValueError("Baseline requires non-empty training and validation series.")

    previous = np.concatenate(
        (
            np.asarray([train_series.iloc[-1]], dtype=float),
            np.asarray(validation_series.iloc[:-1], dtype=float),
        )
    )
    return previous


def compute_metrics(
    actuals: np.ndarray | pd.Series, predictions: np.ndarray | pd.Series
) -> EvaluationMetrics:
    """Compute MAE, MSE, RMSE and R² with explicit numpy formulas."""

    actual = np.asarray(actuals, dtype=float).reshape(-1)
    predicted = np.asarray(predictions, dtype=float).reshape(-1)
    if actual.size == 0 or predicted.size == 0:
        raise ValueError("Metrics require non-empty actual and predicted values.")
    if actual.shape != predicted.shape:
        raise ValueError("Actual and predicted values must have the same length.")
    if not np.isfinite(actual).all() or not np.isfinite(predicted).all():
        raise ValueError("Metrics require finite actual and predicted values.")

    errors = actual - predicted
    mae = float(np.mean(np.abs(errors)))
    mse = float(np.mean(errors**2))
    rmse = float(np.sqrt(mse))

    variance = float(np.var(actual))
    if variance == 0.0:
        r2: float | None = None
    else:
        total = float(np.sum((actual - np.mean(actual)) ** 2))
        residual = float(np.sum(errors**2))
        r2 = 1.0 - residual / total

    return EvaluationMetrics(
        mae=mae,
        mse=mse,
        rmse=rmse,
        r2=r2,
        observation_count=int(actual.size),
    )


def build_evaluation_report(
    *,
    dataset_fingerprint: str,
    split: ChronologicalSplit,
    configuration: ARIMAConfiguration,
    actuals: np.ndarray | pd.Series,
    model_predictions: np.ndarray | pd.Series,
    baseline_predictions: np.ndarray | pd.Series,
    preprocessing: PreprocessingSummary,
    limitations: list[str],
    generated_at: str | None = None,
) -> EvaluationReport:
    """Build the complete validation report for both forecasting approaches."""

    model_metrics = compute_metrics(actuals, model_predictions)
    baseline_metrics = compute_metrics(actuals, baseline_predictions)
    return EvaluationReport(
        generated_at=generated_at or datetime.now(UTC).isoformat(timespec="seconds"),
        dataset_fingerprint=dataset_fingerprint,
        split=split,
        model=configuration,
        model_metrics=model_metrics,
        baseline_metrics=baseline_metrics,
        outperforms_baseline_rmse=model_metrics.rmse < baseline_metrics.rmse,
        preprocessing=preprocessing,
        limitations=list(limitations),
    )
