"""Atomic artifact persistence for models, reports and validation predictions."""

from __future__ import annotations

import json
import os
import pickle
import tempfile
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd

from btc_forecast.config import (
    EVALUATION_REPORT_NAME,
    MODEL_ARTIFACT_NAME,
    VALIDATION_PREDICTIONS_NAME,
)
from btc_forecast.evaluation import EvaluationReport


class ArtifactError(RuntimeError):
    """Raised when an artifact cannot be written or loaded."""


REQUIRED_ARTIFACT_KEYS = (
    "artifact_version",
    "created_at",
    "model",
    "model_name",
    "order",
    "target",
    "horizon_days",
    "evaluation_training_range",
    "validation_range",
    "production_training_range",
    "last_observed_date",
    "next_forecast_date",
    "dataset_fingerprint",
    "preprocessing",
    "evaluation",
)


def _atomic_write(path: Path, writer: Callable[[object], None]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            writer(handle)
        os.replace(temporary_path, path)
    except Exception as exc:
        temporary_path.unlink(missing_ok=True)
        raise ArtifactError(f"Could not write artifact {path}: {exc}") from exc
    return path


def save_model_artifact(path: str | Path, payload: dict[str, object]) -> Path:
    """Pickle the fitted production model and its metadata atomically."""

    def writer(handle: object) -> None:
        pickle.dump(payload, handle, protocol=pickle.HIGHEST_PROTOCOL)  # type: ignore[arg-type]

    return _atomic_write(Path(path), writer)


def save_evaluation_json(path: str | Path, report: EvaluationReport) -> Path:
    """Write the evaluation report as UTF-8 JSON atomically."""

    def writer(handle: object) -> None:
        text = json.dumps(report.to_dict(), indent=2, ensure_ascii=False)
        handle.write(text.encode("utf-8"))  # type: ignore[attr-defined]

    return _atomic_write(Path(path), writer)


def save_validation_predictions(path: str | Path, rows: pd.DataFrame) -> Path:
    """Write validation actuals and both prediction columns atomically."""

    def writer(handle: object) -> None:
        handle.write(rows.to_csv(index=False).encode("utf-8"))  # type: ignore[attr-defined]

    return _atomic_write(Path(path), writer)


def save_artifacts(
    artifacts_dir: str | Path,
    *,
    model_payload: dict[str, object],
    report: EvaluationReport,
    predictions: pd.DataFrame,
) -> dict[str, Path]:
    """Write the three artifacts, removing newly written files on failure."""

    directory = Path(artifacts_dir)
    written: list[Path] = []
    try:
        model_path = save_model_artifact(directory / MODEL_ARTIFACT_NAME, model_payload)
        written.append(model_path)
        report_path = save_evaluation_json(directory / EVALUATION_REPORT_NAME, report)
        written.append(report_path)
        predictions_path = save_validation_predictions(
            directory / VALIDATION_PREDICTIONS_NAME, predictions
        )
        written.append(predictions_path)
    except Exception:
        for path in written:
            path.unlink(missing_ok=True)
        raise

    return {
        MODEL_ARTIFACT_NAME: model_path,
        EVALUATION_REPORT_NAME: report_path,
        VALIDATION_PREDICTIONS_NAME: predictions_path,
    }


def _is_date_range(value: object) -> bool:
    return (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and all(isinstance(item, str) and item for item in value)
    )


def load_model_artifact(
    path: str | Path, expected_fingerprint: str | None = None
) -> dict[str, object]:
    """Load and validate a persisted model artifact before inference."""

    artifact_path = Path(path)
    if not artifact_path.is_file():
        raise ArtifactError(f"Model artifact not found: {artifact_path}")

    try:
        with artifact_path.open("rb") as handle:
            payload = pickle.load(handle)
    except Exception as exc:
        raise ArtifactError(
            f"Model artifact is corrupt or unreadable: {artifact_path}: {exc}"
        ) from exc

    if not isinstance(payload, dict):
        raise ArtifactError(
            f"Model artifact must contain a dictionary, found {type(payload).__name__}."
        )

    version = payload.get("artifact_version")
    if version != 1:
        raise ArtifactError(f"Unsupported artifact version {version!r}; expected 1.")

    missing = [key for key in REQUIRED_ARTIFACT_KEYS if key not in payload]
    if missing:
        raise ArtifactError(
            "Model artifact is missing required key(s): " + ", ".join(missing) + "."
        )

    order = payload.get("order")
    if (
        not isinstance(order, (list, tuple))
        or len(order) != 3
        or any(not isinstance(value, int) or value < 0 for value in order)
    ):
        raise ArtifactError(
            "Model artifact order must contain three non-negative integers."
        )

    if not _is_date_range(payload.get("evaluation_training_range")):
        raise ArtifactError("Model artifact has an invalid evaluation training range.")
    if not _is_date_range(payload.get("validation_range")):
        raise ArtifactError("Model artifact has an invalid validation range.")
    if not _is_date_range(payload.get("production_training_range")):
        raise ArtifactError("Model artifact has an invalid production training range.")
    if not all(
        isinstance(payload.get(key), str)
        for key in (
            "created_at",
            "model_name",
            "target",
            "last_observed_date",
            "next_forecast_date",
            "dataset_fingerprint",
        )
    ):
        raise ArtifactError("Model artifact contains a non-string metadata field.")
    if payload.get("target") != "close_USD":
        raise ArtifactError("Model artifact target must be 'close_USD'.")
    if payload.get("horizon_days") != 1:
        raise ArtifactError("Model artifact horizon_days must be 1.")
    if not isinstance(payload.get("preprocessing"), dict):
        raise ArtifactError(
            "Model artifact preprocessing metadata must be a dictionary."
        )
    if not isinstance(payload.get("evaluation"), dict):
        raise ArtifactError("Model artifact evaluation metadata must be a dictionary.")

    stored_fingerprint = payload.get("dataset_fingerprint")
    if expected_fingerprint and stored_fingerprint != expected_fingerprint:
        raise ArtifactError(
            "Model artifact dataset fingerprint does not match the current source "
            f"dataset ({stored_fingerprint!r} != {expected_fingerprint!r})."
        )

    try:
        forecast = payload["model"].get_forecast(steps=1).predicted_mean  # type: ignore[attr-defined]
        value = float(np.asarray(forecast, dtype=float).reshape(-1)[0])
    except Exception as exc:
        raise ArtifactError(
            "Model artifact cannot produce a one-step forecast: " + str(exc)
        ) from exc
    if not np.isfinite(value):
        raise ArtifactError("Model artifact produced a non-finite one-step forecast.")

    return payload
