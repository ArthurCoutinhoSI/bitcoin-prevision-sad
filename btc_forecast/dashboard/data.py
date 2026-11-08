"""Dashboard data assembly and state detection; contains no Streamlit imports."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from btc_forecast.config import (
    DEFAULT_ARTIFACTS_DIR,
    DEFAULT_DATA_PATH,
    EVALUATION_REPORT_NAME,
    MODEL_ARTIFACT_NAME,
    VALIDATION_PREDICTIONS_NAME,
)
from btc_forecast.data import DataError, load_csv
from btc_forecast.insights import (
    Forecast,
    Insight,
    build_forecast,
    build_insight_from_values,
)
from btc_forecast.model import ModelError, forecast_next_day
from btc_forecast.persistence import ArtifactError, load_model_artifact
from btc_forecast.preprocessing import (
    PreprocessingSummary,
    clean_dataset,
)


@dataclass
class DashboardView:
    """Everything the dashboard needs for one render."""

    status: str
    message: str
    history: pd.DataFrame | None = None
    forecast: Forecast | None = None
    metrics: dict[str, object] | None = None
    insights: Insight | None = None
    validation_predictions: pd.DataFrame | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class DashboardData:
    """Cleaned history plus the fingerprint used to validate artifacts."""

    history: pd.DataFrame
    fingerprint: str


def _summary_from_dict(payload: dict[str, object]) -> PreprocessingSummary:
    date_range = payload.get("date_range")
    if not isinstance(date_range, (list, tuple)) or len(date_range) != 2:
        raise ValueError("Invalid preprocessing date range.")
    return PreprocessingSummary(
        source_count=int(payload["source_count"]),
        accepted_count=int(payload["accepted_count"]),
        rejected_count=int(payload["rejected_count"]),
        duplicates_removed=int(payload["duplicates_removed"]),
        missing_values_imputed=int(payload["missing_values_imputed"]),
        rows_excluded_without_prior_value=int(
            payload["rows_excluded_without_prior_value"]
        ),
        date_range=(str(date_range[0]), str(date_range[1])),
        actions=[str(item) for item in payload.get("actions", [])],
    )


def _metric(metrics: dict[str, object], section: str, key: str) -> float:
    section_payload = metrics.get(section)
    if not isinstance(section_payload, dict) or key not in section_payload:
        raise ValueError(f"Missing evaluation metric {section}.{key}.")
    value = float(section_payload[key])
    return value


def _message_for_missing(path: Path) -> str:
    return (
        f"No model artifact found at {path}. Run "
        "`python -m btc_forecast.cli train --data dc.csv --artifacts artifacts` "
        "to generate one. No forecast is shown on purpose."
    )


def load_dashboard_data(
    data_path: str | Path = DEFAULT_DATA_PATH,
) -> DashboardData:
    """Load and clean the source CSV; raises ``DataError`` when unreadable."""

    raw, dataset = load_csv(Path(data_path))
    cleaned, _ = clean_dataset(raw)
    return DashboardData(
        history=cleaned[["date", "close_USD"]].copy(),
        fingerprint=dataset.fingerprint,
    )


def load_dashboard_view(
    data_path: str | Path = DEFAULT_DATA_PATH,
    artifacts_dir: str | Path = DEFAULT_ARTIFACTS_DIR,
    *,
    data: DashboardData | None = None,
    artifact: dict[str, object] | None = None,
) -> DashboardView:
    """Load artifacts and assemble the dashboard view with an explicit state.

    ``data`` and ``artifact`` may be supplied by the caller (for example from
    Streamlit caches) to avoid re-reading files on every render.
    """

    directory = Path(artifacts_dir)

    if data is None:
        try:
            data = load_dashboard_data(data_path)
        except DataError as exc:
            return DashboardView(status="data_error", message=str(exc))
        except Exception as exc:  # noqa: BLE001 - report any read failure
            return DashboardView(
                status="data_error", message=f"Could not read the source dataset: {exc}"
            )

    history = data.history
    model_path = directory / MODEL_ARTIFACT_NAME
    if artifact is None:
        if not model_path.is_file():
            return DashboardView(
                status="missing_artifacts",
                message=_message_for_missing(model_path),
                history=history,
            )

        try:
            artifact = load_model_artifact(model_path, data.fingerprint)
        except ArtifactError as exc:
            return DashboardView(
                status="invalid_artifacts", message=str(exc), history=history
            )
    elif artifact.get("dataset_fingerprint") != data.fingerprint:
        return DashboardView(
            status="invalid_artifacts",
            message=(
                "Model artifact dataset fingerprint does not match the current "
                "source dataset. Re-run training before opening the dashboard."
            ),
            history=history,
        )

    optional_missing: list[str] = []
    evaluation_path = directory / EVALUATION_REPORT_NAME
    if evaluation_path.is_file():
        try:
            evaluation_file = json.loads(evaluation_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return DashboardView(
                status="invalid_artifacts",
                message=f"Evaluation report is unreadable: {exc}",
                history=history,
            )
        if evaluation_file.get("dataset_fingerprint") != data.fingerprint:
            return DashboardView(
                status="invalid_artifacts",
                message=(
                    "Evaluation report fingerprint does not match the current "
                    "dataset. Re-run training."
                ),
                history=history,
            )
    else:
        optional_missing.append(EVALUATION_REPORT_NAME)

    predictions: pd.DataFrame | None = None
    predictions_path = directory / VALIDATION_PREDICTIONS_NAME
    if predictions_path.is_file():
        try:
            predictions = pd.read_csv(predictions_path)
            required = {
                "date",
                "actual_close",
                "model_prediction",
                "baseline_prediction",
            }
            if not required <= set(predictions.columns) or predictions.empty:
                raise ValueError("unexpected columns or no rows")
        except (OSError, ValueError, pd.errors.ParserError):
            predictions = None
            optional_missing.append(VALIDATION_PREDICTIONS_NAME)
    else:
        optional_missing.append(VALIDATION_PREDICTIONS_NAME)

    try:
        raw_forecast = forecast_next_day(artifact)
        forecast = build_forecast(
            target_date=str(raw_forecast["target_date"]),
            predicted_close=float(raw_forecast["predicted_close"]),
            last_observed_close=float(raw_forecast["last_observed_close"]),
            model_name=str(raw_forecast["model_name"]),
            generated_at=str(raw_forecast["generated_at"]),
        )
    except (ModelError, ValueError, KeyError, TypeError) as exc:
        return DashboardView(
            status="invalid_artifacts",
            message=f"Artifact cannot produce a valid forecast: {exc}",
            history=history,
        )

    evaluation = artifact.get("evaluation")
    if not isinstance(evaluation, dict):
        return DashboardView(
            status="invalid_artifacts",
            message="Artifact evaluation metadata is invalid.",
            history=history,
        )

    try:
        model_rmse = _metric(evaluation, "model_metrics", "rmse")
        baseline_rmse = _metric(evaluation, "baseline_metrics", "rmse")
        preprocessing_payload = artifact.get("preprocessing")
        if not isinstance(preprocessing_payload, dict):
            raise TypeError("Artifact preprocessing metadata must be a dictionary.")
        preprocessing = _summary_from_dict(preprocessing_payload)
        insights = build_insight_from_values(
            forecast=forecast,
            model_rmse=model_rmse,
            baseline_rmse=baseline_rmse,
            outperforms_baseline_rmse=bool(evaluation.get("outperforms_baseline_rmse")),
            limitations=[str(item) for item in evaluation.get("limitations", [])],
            preprocessing=preprocessing,
        )
    except (ValueError, KeyError, TypeError) as exc:
        return DashboardView(
            status="invalid_artifacts",
            message=f"Artifact metadata is incomplete: {exc}",
            history=history,
        )

    metadata: dict[str, object] = {
        "artifact_version": int(artifact.get("artifact_version", 0)),
        "model_name": str(artifact.get("model_name", "ARIMA")),
        "order": list(artifact.get("order", [])),
        "created_at": str(artifact.get("created_at", "")),
        "dataset_fingerprint": str(artifact.get("dataset_fingerprint", "")),
        "last_observed_date": str(artifact.get("last_observed_date", "")),
        "next_forecast_date": str(artifact.get("next_forecast_date", "")),
        "evaluation_training_range": list(
            artifact.get("evaluation_training_range", [])
        ),
        "validation_range": list(artifact.get("validation_range", [])),
        "data_range": list(preprocessing.date_range),
    }

    if optional_missing:
        message = (
            "Forecast and metrics are loaded from model.pkl. Optional file(s) "
            "missing or unreadable: " + ", ".join(optional_missing) + "."
        )
        return DashboardView(
            status="partial_artifacts",
            message=message,
            history=history,
            forecast=forecast,
            metrics=evaluation,
            insights=insights,
            validation_predictions=predictions,
            metadata=metadata,
        )

    return DashboardView(
        status="ready",
        message="Forecast loaded from the persisted model.",
        history=history,
        forecast=forecast,
        metrics=evaluation,
        insights=insights,
        validation_predictions=predictions,
        metadata=metadata,
    )
