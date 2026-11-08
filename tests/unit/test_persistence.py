from __future__ import annotations

import pickle
from pathlib import Path

import pytest

from btc_forecast.data import load_csv
from btc_forecast.model import forecast_next_day
from btc_forecast.persistence import ArtifactError, load_model_artifact
from btc_forecast.pipeline import run_training

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "dc_sample.csv"


@pytest.fixture(scope="module")
def artifact_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    directory = tmp_path_factory.mktemp("artifacts")
    run_training(FIXTURE, directory)
    return directory


@pytest.fixture(scope="module")
def valid_artifact(artifact_dir: Path) -> dict[str, object]:
    with (artifact_dir / "model.pkl").open("rb") as handle:
        return pickle.load(handle)


def rewrite(directory: Path, payload: object) -> Path:
    path = directory / "model.pkl"
    with path.open("wb") as handle:
        pickle.dump(payload, handle)
    return path


def expected_fingerprint() -> str:
    _, dataset = load_csv(FIXTURE)
    return dataset.fingerprint


def test_valid_artifact_loads_and_forecasts(
    artifact_dir: Path, valid_artifact: dict[str, object]
) -> None:
    loaded = load_model_artifact(artifact_dir / "model.pkl", expected_fingerprint())
    forecast = forecast_next_day(loaded)

    assert loaded["artifact_version"] == 1
    assert loaded["target"] == "close_USD"
    assert loaded["horizon_days"] == 1
    assert forecast["target_date"] == "2020-04-10"
    assert forecast["predicted_close"] > 0


def test_missing_artifact_fails(tmp_path: Path) -> None:
    with pytest.raises(ArtifactError, match="not found"):
        load_model_artifact(tmp_path / "model.pkl", expected_fingerprint())


def test_corrupt_artifact_fails(tmp_path: Path) -> None:
    path = tmp_path / "model.pkl"
    path.write_text("not a pickle")

    with pytest.raises(ArtifactError, match="corrupt|unreadable"):
        load_model_artifact(path, expected_fingerprint())


def test_non_dictionary_root_fails(tmp_path: Path) -> None:
    path = rewrite(tmp_path, [1, 2, 3])

    with pytest.raises(ArtifactError, match="dictionary"):
        load_model_artifact(path, expected_fingerprint())


def test_wrong_version_fails(tmp_path: Path, valid_artifact: dict[str, object]) -> None:
    payload = dict(valid_artifact)
    payload["artifact_version"] = 99
    path = rewrite(tmp_path, payload)

    with pytest.raises(ArtifactError, match="version"):
        load_model_artifact(path, expected_fingerprint())


def test_missing_key_fails(tmp_path: Path, valid_artifact: dict[str, object]) -> None:
    payload = dict(valid_artifact)
    payload.pop("model")
    path = rewrite(tmp_path, payload)

    with pytest.raises(ArtifactError, match="model"):
        load_model_artifact(path, expected_fingerprint())


def test_invalid_order_fails(tmp_path: Path, valid_artifact: dict[str, object]) -> None:
    payload = dict(valid_artifact)
    payload["order"] = [1, -1]
    path = rewrite(tmp_path, payload)

    with pytest.raises(ArtifactError, match="order"):
        load_model_artifact(path, expected_fingerprint())


def test_fingerprint_mismatch_fails(
    artifact_dir: Path, valid_artifact: dict[str, object]
) -> None:
    with pytest.raises(ArtifactError, match="fingerprint"):
        load_model_artifact(artifact_dir / "model.pkl", "sha256:different")
