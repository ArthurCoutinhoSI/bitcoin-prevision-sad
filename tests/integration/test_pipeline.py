from __future__ import annotations

import json
import pickle
from pathlib import Path

import pandas as pd
import pytest

from btc_forecast.cli import main
from btc_forecast.pipeline import run_training

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "dc_sample.csv"


def test_training_produces_all_artifacts(tmp_path: Path) -> None:
    result = run_training(FIXTURE, tmp_path)

    assert result.report.model_metrics.observation_count == 20
    assert result.report.baseline_metrics.observation_count == 20
    assert result.configuration.order in [
        (p, d, q) for p in (0, 1, 2) for d in (0, 1) for q in (0, 1, 2)
    ]

    for name in ("model.pkl", "evaluation.json", "validation_predictions.csv"):
        assert (tmp_path / name).is_file(), name

    report = json.loads((tmp_path / "evaluation.json").read_text())
    assert report["split"]["train_count"] == 80
    assert report["split"]["validation_count"] == 20
    assert report["model_metrics"]["observation_count"] == 20
    assert report["baseline_metrics"]["observation_count"] == 20

    predictions = pd.read_csv(tmp_path / "validation_predictions.csv")
    assert len(predictions) == 20
    assert predictions["date"].is_unique
    assert predictions["date"].is_monotonic_increasing
    assert {"actual_close", "model_prediction", "baseline_prediction"} <= set(
        predictions.columns
    )

    with (tmp_path / "model.pkl").open("rb") as handle:
        artifact = pickle.load(handle)
    assert artifact["artifact_version"] == 1
    assert artifact["model_name"] == "ARIMA"
    assert artifact["target"] == "close_USD"
    assert artifact["horizon_days"] == 1
    assert len(artifact["order"]) == 3


def test_predict_uses_persisted_model_without_training(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run_training(FIXTURE, tmp_path)

    code = main(
        [
            "predict",
            "--artifacts",
            str(tmp_path),
            "--data",
            str(FIXTURE),
            "--json",
        ]
    )
    captured = capsys.readouterr()

    assert code == 0
    payload = json.loads(captured.out)
    assert payload["target_date"] == "2020-04-10"
    assert payload["model_name"] == "ARIMA"
    assert payload["predicted_close"] > 0
    assert payload["direction"] in {"up", "down", "flat"}
    assert {
        "target_date",
        "predicted_close",
        "last_observed_close",
        "direction",
        "percentage_change",
        "model_name",
        "generated_at",
    } <= set(payload)


def test_predict_without_artifact_exits_4(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(
        [
            "predict",
            "--artifacts",
            str(tmp_path),
            "--data",
            str(FIXTURE),
            "--json",
        ]
    )
    captured = capsys.readouterr()

    assert code == 4
    assert "not found" in captured.err


def test_training_is_deterministic_within_tolerance(tmp_path: Path) -> None:
    first = run_training(FIXTURE, tmp_path / "first")
    second = run_training(FIXTURE, tmp_path / "second")

    assert first.report.model_metrics.rmse == pytest.approx(
        second.report.model_metrics.rmse, abs=1e-6
    )
    assert first.report.model_metrics.mae == pytest.approx(
        second.report.model_metrics.mae, abs=1e-6
    )
    assert first.report.baseline_metrics.rmse == pytest.approx(
        second.report.baseline_metrics.rmse, abs=1e-6
    )
