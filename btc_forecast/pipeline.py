"""End-to-end training, evaluation and persistence orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd

from btc_forecast.config import (
    DEFAULT_ARTIFACTS_DIR,
    DEFAULT_DATA_PATH,
    HORIZON_DAYS,
    LIMITATIONS,
    TARGET_COLUMN,
)
from btc_forecast.data import Dataset, load_csv
from btc_forecast.evaluation import (
    EvaluationReport,
    baseline_predictions,
    build_evaluation_report,
)
from btc_forecast.model import (
    ARIMAConfiguration,
    ChronologicalSplit,
    refit_production,
    select_arima_order,
    series_from_records,
    split_chronological,
    walk_forward_predictions,
)
from btc_forecast.persistence import save_artifacts
from btc_forecast.preprocessing import PreprocessingSummary, clean_dataset


@dataclass(frozen=True)
class TrainingResult:
    """Everything produced by a successful training run."""

    dataset: Dataset
    preprocessing: PreprocessingSummary
    split: ChronologicalSplit
    configuration: ARIMAConfiguration
    report: EvaluationReport
    artifacts: dict[str, Path]


def run_training(
    data_path: str | Path = DEFAULT_DATA_PATH,
    artifacts_dir: str | Path = DEFAULT_ARTIFACTS_DIR,
) -> TrainingResult:
    """Validate, clean, train, evaluate, refit and persist the model."""

    raw, dataset = load_csv(data_path)
    cleaned, preprocessing = clean_dataset(raw)
    split = split_chronological(cleaned)

    configuration = select_arima_order(split.train)
    model_predictions = walk_forward_predictions(split, configuration.order)
    baseline = baseline_predictions(split.train, split.validation)
    actuals = split.validation.to_numpy(dtype=float)

    report = build_evaluation_report(
        dataset_fingerprint=dataset.fingerprint,
        split=split,
        configuration=configuration,
        actuals=actuals,
        model_predictions=model_predictions,
        baseline_predictions=baseline,
        preprocessing=preprocessing,
        limitations=list(LIMITATIONS),
    )

    full_series = series_from_records(cleaned)
    production_model = refit_production(full_series, configuration.order)

    last_observed = cleaned["date"].max().date()
    next_forecast = last_observed + timedelta(days=HORIZON_DAYS)
    created_at = datetime.now(UTC).isoformat(timespec="seconds")

    model_payload: dict[str, object] = {
        "artifact_version": 1,
        "created_at": created_at,
        "model": production_model,
        "model_name": "ARIMA",
        "order": list(configuration.order),
        "target": TARGET_COLUMN,
        "horizon_days": HORIZON_DAYS,
        "evaluation_training_range": list(split.train_range),
        "validation_range": list(split.validation_range),
        "production_training_range": [
            cleaned["date"].min().date().isoformat(),
            last_observed.isoformat(),
        ],
        "last_observed_date": last_observed.isoformat(),
        "next_forecast_date": next_forecast.isoformat(),
        "dataset_fingerprint": dataset.fingerprint,
        "preprocessing": preprocessing.to_dict(),
        "evaluation": report.to_dict(),
    }

    predictions = pd.DataFrame(
        {
            "date": split.validation.index.strftime("%Y-%m-%d"),
            "actual_close": actuals,
            "model_prediction": model_predictions,
            "baseline_prediction": baseline,
        }
    )

    artifacts = save_artifacts(
        artifacts_dir,
        model_payload=model_payload,
        report=report,
        predictions=predictions,
    )

    return TrainingResult(
        dataset=dataset,
        preprocessing=preprocessing,
        split=split,
        configuration=configuration,
        report=report,
        artifacts=artifacts,
    )
