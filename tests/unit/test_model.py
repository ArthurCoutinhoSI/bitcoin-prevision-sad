from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from btc_forecast.model import (
    ModelError,
    fit_arima,
    refit_production,
    select_arima_order,
    split_chronological,
    walk_forward_predictions,
)


def make_records(count: int = 1000) -> pd.DataFrame:
    dates = pd.date_range("2018-05-07", periods=count, freq="D")
    values = (
        10000.0 + np.arange(count, dtype=float) + 250.0 * np.sin(np.arange(count) / 9.0)
    )
    return pd.DataFrame({"date": dates, "close_USD": values})


def test_split_is_chronological_80_20() -> None:
    split = split_chronological(make_records(1000))

    assert split.train_count == 800
    assert split.validation_count == 200
    assert split.train.index.max() < split.validation.index.min()
    assert split.train_range == ("2018-05-07", "2020-07-14")
    assert split.validation_range == ("2020-07-15", "2021-01-30")
    assert split.split_method == "chronological"
    assert split.to_dict()["train_count"] == 800


def test_selection_uses_fixed_grid_and_returns_configuration() -> None:
    records = make_records(120)
    split = split_chronological(records, train_ratio=0.8)

    config = select_arima_order(split.train, grid={"p": (1,), "d": (1,), "q": (1,)})

    assert config.order == (1, 1, 1)
    assert config.selection_method == "AIC"
    assert np.isfinite(config.aic)
    assert config.fitted_on == split.train_range


def test_selection_fails_when_no_candidate_fits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records = make_records(40)
    split = split_chronological(records)

    def fail(*args, **kwargs):
        raise ModelError("candidate failed")

    monkeypatch.setattr("btc_forecast.model.fit_arima", fail)

    with pytest.raises(ModelError, match="No ARIMA candidate"):
        select_arima_order(split.train, grid={"p": (1,), "d": (1,), "q": (1,)})


def test_walk_forward_uses_only_prior_actuals() -> None:
    split = split_chronological(make_records(120))

    predictions = walk_forward_predictions(split, (1, 1, 1))
    first_fit = fit_arima(split.train, (1, 1, 1))
    expected_first = float(
        np.asarray(first_fit.get_forecast(steps=1).predicted_mean).reshape(-1)[0]
    )

    assert len(predictions) == split.validation_count
    assert np.isfinite(predictions).all()
    assert predictions[0] == pytest.approx(expected_first)


def test_production_refit_uses_all_records() -> None:
    records = make_records(60)
    split = split_chronological(records)
    model_series = split.train

    fitted = refit_production(model_series, (0, 1, 1))

    assert len(fitted.params) > 0
    assert fitted.nobs == len(model_series)


def test_split_rejects_too_few_records() -> None:
    with pytest.raises(ModelError, match="At least"):
        split_chronological(make_records(3))
