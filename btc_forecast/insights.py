"""Forecast interpretation, comparison and data-quality insights."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from math import isfinite

from btc_forecast.config import DISCLAIMER
from btc_forecast.evaluation import EvaluationReport
from btc_forecast.preprocessing import PreprocessingSummary


@dataclass(frozen=True)
class Forecast:
    """A next-day forecast with direction and relative change."""

    target_date: str
    predicted_close: float
    last_observed_close: float
    direction: str
    percentage_change: float
    model_name: str
    generated_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "target_date": self.target_date,
            "predicted_close": self.predicted_close,
            "last_observed_close": self.last_observed_close,
            "direction": self.direction,
            "percentage_change": self.percentage_change,
            "model_name": self.model_name,
            "generated_at": self.generated_at,
        }


@dataclass(frozen=True)
class Insight:
    """Plain-language interpretation of the forecast and its limitations."""

    direction: str
    percentage_change: float
    model_vs_baseline: str
    data_quality: str
    limitations: list[str]
    disclaimer: str

    def to_dict(self) -> dict[str, object]:
        return {
            "direction": self.direction,
            "percentage_change": self.percentage_change,
            "model_vs_baseline": self.model_vs_baseline,
            "data_quality": self.data_quality,
            "limitations": list(self.limitations),
            "disclaimer": self.disclaimer,
        }


def build_forecast(
    *,
    target_date: str,
    predicted_close: float,
    last_observed_close: float,
    model_name: str = "ARIMA",
    generated_at: str | None = None,
) -> Forecast:
    """Build a forecast and derive direction from the relative price change."""

    predicted = float(predicted_close)
    last = float(last_observed_close)
    if not isfinite(predicted) or not isfinite(last):
        raise ValueError("Forecast requires finite predicted and last observed closes.")
    if last <= 0:
        raise ValueError("Last observed close must be positive.")

    change = (predicted - last) / last
    if change > 0:
        direction = "up"
    elif change < 0:
        direction = "down"
    else:
        direction = "flat"

    return Forecast(
        target_date=target_date,
        predicted_close=predicted,
        last_observed_close=last,
        direction=direction,
        percentage_change=change,
        model_name=model_name,
        generated_at=generated_at or datetime.now(UTC).isoformat(timespec="seconds"),
    )


def build_insight_from_values(
    *,
    forecast: Forecast,
    model_rmse: float,
    baseline_rmse: float,
    outperforms_baseline_rmse: bool,
    limitations: list[str],
    preprocessing: PreprocessingSummary,
) -> Insight:
    """Summarize direction, model quality, data quality and limitations."""

    if outperforms_baseline_rmse:
        comparison = (
            "ARIMA achieved a lower validation RMSE than the naive last-value "
            f"baseline ({model_rmse:.2f} vs {baseline_rmse:.2f})."
        )
    else:
        comparison = (
            "The naive last-value baseline achieved a lower validation RMSE than "
            f"ARIMA ({baseline_rmse:.2f} vs {model_rmse:.2f})."
        )

    data_quality = (
        f"{preprocessing.accepted_count} accepted records from "
        f"{preprocessing.date_range[0]} to {preprocessing.date_range[1]}; "
        f"{preprocessing.duplicates_removed} exact duplicate row(s) removed; "
        f"{preprocessing.missing_values_imputed} missing price value(s) "
        "forward-filled."
    )

    return Insight(
        direction=forecast.direction,
        percentage_change=forecast.percentage_change,
        model_vs_baseline=comparison,
        data_quality=data_quality,
        limitations=list(limitations),
        disclaimer=DISCLAIMER,
    )


def build_insight(
    *,
    report: EvaluationReport,
    forecast: Forecast,
    preprocessing: PreprocessingSummary,
) -> Insight:
    """Build an insight from an evaluation report object."""

    return build_insight_from_values(
        forecast=forecast,
        model_rmse=report.model_metrics.rmse,
        baseline_rmse=report.baseline_metrics.rmse,
        outperforms_baseline_rmse=report.outperforms_baseline_rmse,
        limitations=report.limitations,
        preprocessing=preprocessing,
    )
