from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from btc_forecast.evaluation import (
    baseline_predictions,
    build_evaluation_report,
    compute_metrics,
)
from btc_forecast.model import ARIMAConfiguration, split_chronological
from btc_forecast.preprocessing import PreprocessingSummary


def test_baseline_repeats_previous_actual_close() -> None:
    train = pd.Series([100.0, 101.0, 102.0])
    validation = pd.Series([103.0, 104.0])

    predicted = baseline_predictions(train, validation)

    assert list(predicted) == [102.0, 103.0]


def test_metrics_match_hand_computed_values() -> None:
    metrics = compute_metrics(np.array([3.0, 5.0]), np.array([2.0, 5.0]))

    assert metrics.mae == pytest.approx(0.5)
    assert metrics.mse == pytest.approx(0.5)
    assert metrics.rmse == pytest.approx(math.sqrt(0.5))
    assert metrics.r2 == pytest.approx(0.5)
    assert metrics.observation_count == 2


def test_r2_is_none_for_zero_variance_actuals() -> None:
    metrics = compute_metrics(np.array([5.0, 5.0]), np.array([4.0, 6.0]))

    assert metrics.r2 is None
    assert metrics.mae == pytest.approx(1.0)


def test_empty_input_is_rejected() -> None:
    with pytest.raises(ValueError, match="empty"):
        compute_metrics(np.array([]), np.array([]))


def test_report_marks_whether_model_beats_baseline() -> None:
    records = pd.DataFrame(
        {
            "date": pd.date_range("2020-01-01", periods=20, freq="D"),
            "close_USD": np.arange(20, dtype=float) + 100.0,
        }
    )
    split = split_chronological(records)
    config = ARIMAConfiguration(
        order=(1, 1, 1),
        aic=1.0,
        fitted_on=split.train_range,
    )
    summary = PreprocessingSummary(
        source_count=20,
        accepted_count=20,
        rejected_count=0,
        duplicates_removed=0,
        missing_values_imputed=0,
        rows_excluded_without_prior_value=0,
        date_range=("2020-01-01", "2020-01-20"),
    )
    actuals = np.array([103.0, 104.0])
    report = build_evaluation_report(
        dataset_fingerprint="sha256:test",
        split=split,
        configuration=config,
        actuals=actuals,
        model_predictions=np.array([103.5, 104.5]),
        baseline_predictions=np.array([102.0, 103.0]),
        preprocessing=summary,
        limitations=["test limitation"],
    )

    assert report.outperforms_baseline_rmse is True
    assert report.model_metrics.observation_count == 2
    payload = report.to_dict()
    assert payload["model"]["order"] == [1, 1, 1]
    assert payload["dataset_fingerprint"] == "sha256:test"
    assert payload["limitations"] == ["test limitation"]
