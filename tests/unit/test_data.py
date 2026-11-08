from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd
import pytest

from btc_forecast.data import DataError, load_csv

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_loads_sample_and_uses_first_column_as_date() -> None:
    frame, dataset = load_csv(FIXTURES / "dc_sample.csv")

    assert "date" in frame.columns
    assert len(frame) == 100
    assert dataset.source_path.endswith("dc_sample.csv")
    assert dataset.record_count == 100
    assert dataset.date_range == ("2020-01-01", "2020-04-09")
    assert dataset.fingerprint.startswith("sha256:")


def test_fingerprint_matches_file_bytes_and_is_stable() -> None:
    path = FIXTURES / "dc_sample.csv"
    expected = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()

    _, first = load_csv(path)
    _, second = load_csv(path)

    assert first.fingerprint == expected
    assert second.fingerprint == expected


def test_missing_target_column_fails(tmp_path: Path) -> None:
    path = tmp_path / "missing_close.csv"
    pd.DataFrame({"": ["2020-01-01"], "open_USD": [100.0]}).to_csv(path, index=False)

    with pytest.raises(DataError, match="close_USD"):
        load_csv(path)


def test_non_numeric_close_fails(tmp_path: Path) -> None:
    path = tmp_path / "bad_close.csv"
    pd.DataFrame({"": ["2020-01-01"], "close_USD": ["not-a-number"]}).to_csv(
        path, index=False
    )

    with pytest.raises(DataError, match="numeric"):
        load_csv(path)


def test_non_positive_close_fails(tmp_path: Path) -> None:
    path = tmp_path / "zero_close.csv"
    pd.DataFrame({"": ["2020-01-01"], "close_USD": [0.0]}).to_csv(path, index=False)

    with pytest.raises(DataError, match="positive"):
        load_csv(path)


def test_unparseable_date_fails(tmp_path: Path) -> None:
    path = tmp_path / "bad_date.csv"
    pd.DataFrame({"": ["not-a-date"], "close_USD": [100.0]}).to_csv(path, index=False)

    with pytest.raises(DataError, match="date"):
        load_csv(path)


def test_missing_file_fails(tmp_path: Path) -> None:
    with pytest.raises(DataError, match="not found"):
        load_csv(tmp_path / "absent.csv")
