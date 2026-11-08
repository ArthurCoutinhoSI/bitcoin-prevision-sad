"""Local command-line interface for training and prediction."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from btc_forecast.config import (
    DEFAULT_ARTIFACTS_DIR,
    DEFAULT_DATA_PATH,
    MODEL_ARTIFACT_NAME,
)
from btc_forecast.data import DataError, load_csv
from btc_forecast.insights import build_forecast
from btc_forecast.model import ModelError, forecast_next_day
from btc_forecast.persistence import ArtifactError, load_model_artifact
from btc_forecast.pipeline import run_training


def _print_metrics(name: str, metrics: dict[str, object]) -> None:
    r2 = metrics["r2"]
    r2_text = "N/A" if r2 is None else f"{float(r2):.6f}"
    print(
        f"  {name:<16} MAE={float(metrics['mae']):.6f} "
        f"MSE={float(metrics['mse']):.6f} "
        f"RMSE={float(metrics['rmse']):.6f} R2={r2_text}"
    )


def _run_train(args: argparse.Namespace) -> int:
    result = run_training(args.data, args.artifacts)
    report = result.report.to_dict()

    print("Training complete.")
    print(
        f"Records: {result.preprocessing.accepted_count} accepted "
        f"({result.preprocessing.source_count} read, "
        f"{result.preprocessing.rejected_count} rejected)"
    )
    print(
        f"Date range: {result.preprocessing.date_range[0]} to "
        f"{result.preprocessing.date_range[1]}"
    )
    print(
        f"Training: {result.split.train_count} rows "
        f"({result.split.train_range[0]} to {result.split.train_range[1]})"
    )
    print(
        f"Validation: {result.split.validation_count} rows "
        f"({result.split.validation_range[0]} to "
        f"{result.split.validation_range[1]})"
    )
    order = result.configuration.order
    print(
        f"Selected ARIMA order: ({order[0]}, {order[1]}, {order[2]}) "
        f"by AIC ({result.configuration.aic:.6f})"
    )
    print("Validation metrics (one-step-ahead):")
    _print_metrics("ARIMA", report["model_metrics"])
    _print_metrics("Naive Last Value", report["baseline_metrics"])
    beats = "yes" if report["outperforms_baseline_rmse"] else "no"
    print(f"ARIMA lower validation RMSE than baseline: {beats}")
    print("Artifacts:")
    for name, path in result.artifacts.items():
        print(f"  {name}: {path}")
    return 0


def _run_predict(args: argparse.Namespace) -> int:
    _, dataset = load_csv(args.data)
    artifact = load_model_artifact(
        args.artifacts / MODEL_ARTIFACT_NAME, dataset.fingerprint
    )
    raw = forecast_next_day(artifact)
    forecast = build_forecast(
        target_date=str(raw["target_date"]),
        predicted_close=float(raw["predicted_close"]),
        last_observed_close=float(raw["last_observed_close"]),
        model_name=str(raw["model_name"]),
        generated_at=str(raw["generated_at"]),
    )

    if args.json:
        print(json.dumps(forecast.to_dict(), indent=2))
        return 0

    print("Next-day forecast")
    print(f"  Target date: {forecast.target_date}")
    print(f"  Predicted close: USD {forecast.predicted_close:,.2f}")
    print(f"  Last observed close: USD {forecast.last_observed_close:,.2f}")
    print(f"  Direction: {forecast.direction}")
    print(f"  Change: {forecast.percentage_change * 100:+.2f}%")
    print(f"  Model: {forecast.model_name}")
    print("  Forecasts are estimates and are not financial advice.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="btc_forecast.cli",
        description="Local Bitcoin next-day forecast training and prediction.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    train_parser = subparsers.add_parser(
        "train", help="Validate, train, evaluate and persist the ARIMA model."
    )
    train_parser.add_argument(
        "--data",
        type=Path,
        default=DEFAULT_DATA_PATH,
        help="Path to the source CSV (default: dc.csv).",
    )
    train_parser.add_argument(
        "--artifacts",
        type=Path,
        default=DEFAULT_ARTIFACTS_DIR,
        help="Directory for generated artifacts (default: artifacts).",
    )
    train_parser.set_defaults(handler=_run_train)

    predict_parser = subparsers.add_parser(
        "predict", help="Generate the next-day forecast from a persisted model."
    )
    predict_parser.add_argument(
        "--artifacts",
        type=Path,
        default=DEFAULT_ARTIFACTS_DIR,
        help="Directory containing model.pkl (default: artifacts).",
    )
    predict_parser.add_argument(
        "--data",
        type=Path,
        default=DEFAULT_DATA_PATH,
        help="Source CSV used to verify the artifact fingerprint (default: dc.csv).",
    )
    predict_parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of a human-readable summary.",
    )
    predict_parser.set_defaults(handler=_run_predict)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return int(args.handler(args))
    except DataError as exc:
        print(f"Invalid data or arguments: {exc}", file=sys.stderr)
        return 2
    except ModelError as exc:
        print(f"Model fitting failed: {exc}", file=sys.stderr)
        return 3
    except ArtifactError as exc:
        print(f"Artifact failure: {exc}", file=sys.stderr)
        return 4
    except Exception as exc:  # noqa: BLE001  # pragma: no cover - final safety net
        print(f"Unexpected failure: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
