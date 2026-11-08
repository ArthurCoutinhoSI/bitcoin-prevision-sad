"""CSV loading, schema validation and dataset fingerprinting."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from btc_forecast.config import DATE_COLUMN, PRICE_COLUMNS, TARGET_COLUMN


class DataError(ValueError):
    """Raised when the source dataset is missing, unreadable or invalid."""


@dataclass(frozen=True)
class Dataset:
    """Metadata for the source dataset."""

    source_path: str
    fingerprint: str
    record_count: int
    date_range: tuple[str, str]
    records: pd.DataFrame


def _fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _normalise_date_column(frame: pd.DataFrame) -> pd.DataFrame:
    first = frame.columns[0]
    if str(first).startswith("Unnamed:") or str(first).strip() == "":
        return frame.rename(columns={first: DATE_COLUMN})
    if str(first).strip().lower() == DATE_COLUMN:
        return frame.rename(columns={first: DATE_COLUMN})
    raise DataError(
        "The first column must be the observation date; "
        f"found column {first!r}. Expected an unnamed date column."
    )


def _numeric_column(frame: pd.DataFrame, column: str) -> pd.Series:
    original = frame[column]
    converted = pd.to_numeric(original, errors="coerce")
    invalid = original.notna() & converted.isna()
    if invalid.any():
        row = int(frame.index[invalid][0]) + 2
        value = original.loc[invalid].iloc[0]
        raise DataError(
            f"Column {column!r} must be numeric; found {value!r} at CSV row {row}."
        )
    return converted


def load_csv(path: str | Path) -> tuple[pd.DataFrame, Dataset]:
    """Load a source CSV and validate the schema and value ranges.

    Returns the typed frame (dates parsed, price columns converted to numbers) and
    the dataset metadata used by later stages.
    """

    source = Path(path)
    if not source.is_file():
        raise DataError(f"Data file not found: {source}")

    try:
        frame = pd.read_csv(source)
    except Exception as exc:  # pragma: no cover - pandas error text is version-specific
        raise DataError(f"Could not read {source}: {exc}") from exc

    if frame.empty:
        raise DataError(f"Data file is empty: {source}")

    frame = _normalise_date_column(frame)
    frame[DATE_COLUMN] = pd.to_datetime(frame[DATE_COLUMN], errors="coerce")
    if frame[DATE_COLUMN].isna().any():
        row = int(frame.index[frame[DATE_COLUMN].isna()][0]) + 2
        raise DataError(
            f"Column 'date' contains an unparseable value at CSV row {row}."
        )

    if TARGET_COLUMN not in frame.columns:
        raise DataError(f"Required column {TARGET_COLUMN!r} is missing from {source}.")

    for column in PRICE_COLUMNS:
        if column not in frame.columns:
            continue
        frame[column] = _numeric_column(frame, column)
        present = frame[column].dropna()
        if (present <= 0).any():
            row = int(frame.index[frame[column] <= 0][0]) + 2
            raise DataError(
                f"Column {column!r} must contain positive values; "
                f"found a non-positive value at CSV row {row}."
            )

    if "volume" in frame.columns:
        volume = _numeric_column(frame, "volume")
        if (volume.dropna() < 0).any():
            raise DataError("Column 'volume' must not contain negative values.")
        frame["volume"] = volume

    dates = frame[DATE_COLUMN]
    dataset = Dataset(
        source_path=str(source),
        fingerprint=_fingerprint(source),
        record_count=len(frame),
        date_range=(
            dates.min().date().isoformat(),
            dates.max().date().isoformat(),
        ),
        records=frame.copy(),
    )
    return frame, dataset
