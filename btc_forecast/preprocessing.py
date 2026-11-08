"""Deterministic cleaning and data-quality summaries."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from btc_forecast.config import (
    DATE_COLUMN,
    OHLC_COLUMNS,
    PRICE_COLUMNS,
    TARGET_COLUMN,
)
from btc_forecast.data import DataError


@dataclass
class PreprocessingSummary:
    """Counts and actions produced while cleaning the dataset."""

    source_count: int
    accepted_count: int
    rejected_count: int
    duplicates_removed: int
    missing_values_imputed: int
    rows_excluded_without_prior_value: int
    date_range: tuple[str, str]
    actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "source_count": self.source_count,
            "accepted_count": self.accepted_count,
            "rejected_count": self.rejected_count,
            "duplicates_removed": self.duplicates_removed,
            "missing_values_imputed": self.missing_values_imputed,
            "rows_excluded_without_prior_value": self.rows_excluded_without_prior_value,
            "date_range": list(self.date_range),
            "actions": list(self.actions),
        }


def _validate_ohlc(frame: pd.DataFrame) -> None:
    available = [column for column in OHLC_COLUMNS if column in frame.columns]
    if len(available) != len(OHLC_COLUMNS):
        return

    complete = frame[available].notna().all(axis=1)
    if not complete.any():
        return

    subset = frame.loc[complete, available]
    lower = subset[["open_USD", "close_USD"]].min(axis=1)
    upper = subset[["open_USD", "close_USD"]].max(axis=1)
    valid = (subset["low_USD"] <= lower) & (upper <= subset["high_USD"])
    if not valid.all():
        bad_date = subset.index[~valid][0]
        raise DataError(
            "OHLC consistency failed for "
            f"{frame.loc[bad_date, DATE_COLUMN].date().isoformat()}: expected "
            "low <= min(open, close) <= max(open, close) <= high."
        )


def clean_dataset(raw_frame: pd.DataFrame) -> tuple[pd.DataFrame, PreprocessingSummary]:
    """Sort, de-duplicate, forward-fill and validate the raw dataset."""

    frame = raw_frame.copy()
    actions: list[str] = []
    source_count = len(frame)

    frame = frame.sort_values(DATE_COLUMN, kind="mergesort").reset_index(drop=True)
    actions.append("Sorted records chronologically in ascending date order.")

    duplicate_mask = frame.duplicated(keep="first")
    duplicates_removed = int(duplicate_mask.sum())
    if duplicates_removed:
        frame = frame.loc[~duplicate_mask].reset_index(drop=True)
        actions.append(f"Removed {duplicates_removed} exact duplicate row(s).")

    repeated = frame[DATE_COLUMN].duplicated(keep=False)
    if repeated.any():
        conflicting = sorted(
            {date.date().isoformat() for date in frame.loc[repeated, DATE_COLUMN]}
        )
        raise DataError(
            "Conflicting duplicate dates found: " + ", ".join(conflicting) + "."
        )

    price_columns = [column for column in PRICE_COLUMNS if column in frame.columns]
    missing_before = int(frame[price_columns].isna().sum().sum())
    frame[price_columns] = frame[price_columns].ffill()
    missing_after = int(frame[price_columns].isna().sum().sum())
    missing_values_imputed = missing_before - missing_after
    if missing_values_imputed:
        actions.append(
            f"Forward-filled {missing_values_imputed} missing price value(s)."
        )

    no_prior_close = frame[TARGET_COLUMN].isna()
    rows_excluded = int(no_prior_close.sum())
    if rows_excluded:
        frame = frame.loc[~no_prior_close].reset_index(drop=True)
        actions.append(f"Excluded {rows_excluded} row(s) without a prior valid close.")

    if frame.empty:
        raise DataError(
            "No usable records remain after cleaning; a valid prior closing price "
            "is required."
        )

    close = frame[TARGET_COLUMN]
    if (close <= 0).any():
        bad_date = frame.index[close <= 0][0]
        raise DataError(
            "Non-positive closing price after cleaning for "
            f"{frame.loc[bad_date, DATE_COLUMN].date().isoformat()}."
        )

    _validate_ohlc(frame)
    actions.append("Validated OHLC consistency for complete records.")

    accepted_count = len(frame)
    summary = PreprocessingSummary(
        source_count=source_count,
        accepted_count=accepted_count,
        rejected_count=source_count - accepted_count,
        duplicates_removed=duplicates_removed,
        missing_values_imputed=missing_values_imputed,
        rows_excluded_without_prior_value=rows_excluded,
        date_range=(
            frame[DATE_COLUMN].min().date().isoformat(),
            frame[DATE_COLUMN].max().date().isoformat(),
        ),
        actions=actions,
    )
    return frame.reset_index(drop=True), summary
