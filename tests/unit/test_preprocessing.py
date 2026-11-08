from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from btc_forecast.data import DataError, load_csv
from btc_forecast.preprocessing import clean_dataset

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def make_frame(rows: list[dict[str, object]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    frame["date"] = pd.to_datetime(frame["date"])
    return frame


def test_sample_is_sorted_and_fully_accepted() -> None:
    raw, _ = load_csv(FIXTURES / "dc_sample.csv")

    cleaned, summary = clean_dataset(raw)

    assert cleaned["date"].is_monotonic_increasing
    assert summary.source_count == 100
    assert summary.accepted_count == 100
    assert summary.rejected_count == 0
    assert summary.duplicates_removed == 0
    assert summary.date_range == ("2020-01-01", "2020-04-09")
    assert summary.actions


def test_exact_duplicates_are_removed_and_counted() -> None:
    raw = make_frame(
        [
            {"date": "2020-01-03", "close_USD": 102.0},
            {"date": "2020-01-02", "close_USD": 101.0},
            {"date": "2020-01-02", "close_USD": 101.0},
            {"date": "2020-01-01", "close_USD": 100.0},
        ]
    )

    cleaned, summary = clean_dataset(raw)

    assert list(cleaned["close_USD"]) == [100.0, 101.0, 102.0]
    assert summary.duplicates_removed == 1
    assert summary.accepted_count == 3
    assert summary.rejected_count == 1


def test_conflicting_duplicate_dates_fail() -> None:
    raw, _ = load_csv(FIXTURES / "invalid_duplicate.csv")

    with pytest.raises(DataError, match="2020-01-02"):
        clean_dataset(raw)


def test_missing_prices_are_forward_filled_and_counted() -> None:
    raw = make_frame(
        [
            {"date": "2020-01-01", "close_USD": 100.0},
            {"date": "2020-01-02", "close_USD": None},
            {"date": "2020-01-03", "close_USD": 103.0},
        ]
    )

    cleaned, summary = clean_dataset(raw)

    assert list(cleaned["close_USD"]) == [100.0, 100.0, 103.0]
    assert summary.missing_values_imputed == 1
    assert summary.rows_excluded_without_prior_value == 0


def test_leading_missing_close_is_excluded_without_future_fill() -> None:
    raw = make_frame(
        [
            {"date": "2020-01-01", "close_USD": None},
            {"date": "2020-01-02", "close_USD": 100.0},
            {"date": "2020-01-03", "close_USD": 101.0},
        ]
    )

    cleaned, summary = clean_dataset(raw)

    assert list(cleaned["close_USD"]) == [100.0, 101.0]
    assert summary.rows_excluded_without_prior_value == 1
    assert summary.missing_values_imputed == 0


def test_invalid_ohlc_fails_with_date() -> None:
    raw, _ = load_csv(FIXTURES / "invalid_ohlc.csv")

    with pytest.raises(DataError, match="2020-01-02"):
        clean_dataset(raw)


def test_summary_serializes_dates() -> None:
    raw, _ = load_csv(FIXTURES / "dc_sample.csv")
    _, summary = clean_dataset(raw)

    payload = summary.to_dict()

    assert payload["date_range"] == ["2020-01-01", "2020-04-09"]
    assert payload["accepted_count"] == 100
