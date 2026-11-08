from __future__ import annotations

import sys
from pathlib import Path

import pytest

from btc_forecast.dashboard.data import load_dashboard_view
from btc_forecast.pipeline import run_training

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "dc_sample.csv"


@pytest.fixture(scope="module")
def trained(tmp_path_factory: pytest.TempPathFactory) -> Path:
    directory = tmp_path_factory.mktemp("dashboard_artifacts")
    run_training(FIXTURE, directory)
    return directory


def test_ready_view_has_forecast_metrics_and_insights(trained: Path) -> None:
    view = load_dashboard_view(FIXTURE, trained)

    assert view.status == "ready"
    assert view.forecast is not None
    assert view.forecast.target_date == "2020-04-10"
    assert view.metrics is not None
    assert view.metrics["model_metrics"]["observation_count"] == 20
    assert view.insights is not None
    assert view.insights.disclaimer
    assert len(view.history) == 100
    assert view.validation_predictions is not None
    assert len(view.validation_predictions) == 20
    assert len(view.metadata["order"]) == 3


def test_missing_artifact_shows_empty_state(tmp_path: Path) -> None:
    view = load_dashboard_view(FIXTURE, tmp_path)

    assert view.status == "missing_artifacts"
    assert view.forecast is None
    assert view.metrics is None
    assert "train" in view.message


def test_corrupt_artifact_shows_invalid_state(trained: Path, tmp_path: Path) -> None:
    (tmp_path / "model.pkl").write_text("not a pickle")

    view = load_dashboard_view(FIXTURE, tmp_path)

    assert view.status == "invalid_artifacts"
    assert view.forecast is None
    assert "corrupt" in view.message.lower() or "unreadable" in view.message.lower()


def test_missing_backtest_file_is_partial(trained: Path, tmp_path: Path) -> None:
    for name in ("model.pkl", "evaluation.json"):
        (tmp_path / name).write_bytes((trained / name).read_bytes())

    view = load_dashboard_view(FIXTURE, tmp_path)

    assert view.status == "partial_artifacts"
    assert view.forecast is not None
    assert view.metrics is not None
    assert view.validation_predictions is None
    assert "validation_predictions.csv" in view.message


def test_fingerprint_mismatch_is_invalid(trained: Path) -> None:
    other = Path(__file__).resolve().parents[2] / "dc.csv"

    view = load_dashboard_view(other, trained)

    assert view.status == "invalid_artifacts"
    assert view.forecast is None


def test_unreadable_data_is_data_error(trained: Path, tmp_path: Path) -> None:
    view = load_dashboard_view(tmp_path / "absent.csv", trained)

    assert view.status == "data_error"
    assert view.forecast is None
    assert "not found" in view.message.lower()


def test_dashboard_data_module_does_not_import_streamlit() -> None:
    assert "streamlit" not in sys.modules
