"""Project-wide constants for data, modeling, evaluation and artifacts."""

from __future__ import annotations

from pathlib import Path

DATE_COLUMN = "date"
TARGET_COLUMN = "close_USD"
HORIZON_DAYS = 1
TRAIN_RATIO = 0.8

PRICE_COLUMNS = (
    "open_USD",
    "high_USD",
    "low_USD",
    "close_USD",
)
OHLC_COLUMNS = ("open_USD", "high_USD", "low_USD", "close_USD")

ARIMA_ORDER_GRID = {
    "p": (0, 1, 2),
    "d": (0, 1),
    "q": (0, 1, 2),
}

ARTIFACT_VERSION = 1
DEFAULT_DATA_PATH = Path("dc.csv")
DEFAULT_ARTIFACTS_DIR = Path("artifacts")
MODEL_ARTIFACT_NAME = "model.pkl"
EVALUATION_REPORT_NAME = "evaluation.json"
VALIDATION_PREDICTIONS_NAME = "validation_predictions.csv"

DISCLAIMER = "Forecasts are estimates, are not guarantees and do not constitute financial advice."

LIMITATIONS = (
    "Univariate ARIMA using only the USD closing price.",
    "Historical dataset covers 2018-05-07 through 2021-01-30.",
    "One-step-ahead metrics do not guarantee future accuracy.",
    "Forecasts are estimates and are not financial advice.",
)
