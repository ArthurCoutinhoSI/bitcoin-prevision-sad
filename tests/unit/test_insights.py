from __future__ import annotations

import re

import pandas as pd
import pytest

from btc_forecast.evaluation import EvaluationMetrics, EvaluationReport
from btc_forecast.insights import build_forecast, build_insight
from btc_forecast.model import ARIMAConfiguration, ChronologicalSplit
from btc_forecast.preprocessing import PreprocessingSummary


def test_direction_up() -> None:
    forecast = build_forecast(
        target_date="2021-01-31",
        predicted_close=110.0,
        last_observed_close=100.0,
    )

    assert forecast.direction == "up"
    assert forecast.percentage_change == pytest.approx(0.10)


def test_direction_down() -> None:
    forecast = build_forecast(
        target_date="2021-01-31",
        predicted_close=90.0,
        last_observed_close=100.0,
    )

    assert forecast.direction == "down"
    assert forecast.percentage_change == pytest.approx(-0.10)


def test_direction_flat() -> None:
    forecast = build_forecast(
        target_date="2021-01-31",
        predicted_close=100.0,
        last_observed_close=100.0,
    )

    assert forecast.direction == "flat"
    assert forecast.percentage_change == 0.0


def test_non_finite_prediction_is_rejected() -> None:
    with pytest.raises(ValueError, match="finite"):
        build_forecast(
            target_date="2021-01-31",
            predicted_close=float("nan"),
            last_observed_close=100.0,
        )


def test_forecast_serializes() -> None:
    forecast = build_forecast(
        target_date="2021-01-31",
        predicted_close=101.0,
        last_observed_close=100.0,
        generated_at="2021-01-30T00:00:00+00:00",
    )

    payload = forecast.to_dict()

    assert payload["target_date"] == "2021-01-31"
    assert payload["direction"] == "up"
    assert payload["model_name"] == "ARIMA"
    assert payload["generated_at"] == "2021-01-30T00:00:00+00:00"


def make_report(*, model_rmse: float, baseline_rmse: float) -> EvaluationReport:
    split = ChronologicalSplit(
        train=pd.Series([100.0, 101.0], index=pd.date_range("2020-01-01", periods=2)),
        validation=pd.Series(
            [102.0, 103.0], index=pd.date_range("2020-01-03", periods=2)
        ),
        train_range=("2020-01-01", "2020-01-02"),
        validation_range=("2020-01-03", "2020-01-04"),
    )
    configuration = ARIMAConfiguration(
        order=(1, 1, 0), aic=1.0, fitted_on=("2020-01-01", "2020-01-02")
    )
    metrics = EvaluationMetrics(
        mae=1.0, mse=1.0, rmse=model_rmse, r2=0.5, observation_count=2
    )
    baseline = EvaluationMetrics(
        mae=1.0, mse=1.0, rmse=baseline_rmse, r2=0.4, observation_count=2
    )
    preprocessing = PreprocessingSummary(
        source_count=4,
        accepted_count=4,
        rejected_count=0,
        duplicates_removed=0,
        missing_values_imputed=0,
        rows_excluded_without_prior_value=0,
        date_range=("2020-01-01", "2020-01-04"),
        actions=["Sorted records."],
    )
    return EvaluationReport(
        generated_at="2020-01-05T00:00:00+00:00",
        dataset_fingerprint="sha256:test",
        split=split,
        model=configuration,
        model_metrics=metrics,
        baseline_metrics=baseline,
        outperforms_baseline_rmse=model_rmse < baseline_rmse,
        preprocessing=preprocessing,
        limitations=["Only the close price is used."],
    )


def test_insight_describes_baseline_comparison_and_data_quality() -> None:
    report = make_report(model_rmse=10.0, baseline_rmse=12.0)
    forecast = build_forecast(
        target_date="2021-01-31",
        predicted_close=101.0,
        last_observed_close=100.0,
    )

    insight = build_insight(
        report=report, forecast=forecast, preprocessing=report.preprocessing
    )

    assert "lower validation RMSE" in insight.model_vs_baseline
    assert "10.00" in insight.model_vs_baseline
    assert "12.00" in insight.model_vs_baseline
    assert "4 accepted records" in insight.data_quality
    assert "2020-01-01 to 2020-01-04" in insight.data_quality
    assert insight.limitations == ["Only the close price is used."]
    assert "financial advice" in insight.disclaimer


def test_insight_reports_when_baseline_wins() -> None:
    report = make_report(model_rmse=12.0, baseline_rmse=10.0)
    forecast = build_forecast(
        target_date="2021-01-31",
        predicted_close=99.0,
        last_observed_close=100.0,
    )

    insight = build_insight(
        report=report, forecast=forecast, preprocessing=report.preprocessing
    )

    assert "baseline achieved a lower validation RMSE" in insight.model_vs_baseline


def test_insight_contains_no_recommendation_language() -> None:
    report = make_report(model_rmse=10.0, baseline_rmse=12.0)
    forecast = build_forecast(
        target_date="2021-01-31",
        predicted_close=101.0,
        last_observed_close=100.0,
    )

    insight = build_insight(
        report=report, forecast=forecast, preprocessing=report.preprocessing
    )
    text = " ".join(str(value) for value in insight.to_dict().values()).lower()

    assert (
        re.search(
            r"\b(buy|sell|hold|recommendation|recommend|price target|trading signal)\b",
            text,
        )
        is None
    )
