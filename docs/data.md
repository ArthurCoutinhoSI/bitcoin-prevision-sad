# Data

## Source

`dc.csv` is the only dataset. It is a local, read-only CSV committed to the repository root and
contains 1000 daily Bitcoin records from `2018-05-07` through `2021-01-30`, stored in descending
date order. The first column has an empty header and represents the observation date.

## Schema

| Column | Type | Used by the model | Rules |
|--------|------|-------------------|-------|
| *(unnamed first column)* | Date | As the index | Must parse as a date; renamed to `date` |
| `open_USD` | Float | No (OHLC validation) | Positive when present |
| `high_USD` | Float | No (OHLC validation) | Positive; `>= max(open, close, low)` |
| `low_USD` | Float | No (OHLC validation) | Positive; `<= min(open, close, high)` |
| `close_USD` | Float | Yes — sole input and target | Required, numeric, positive |
| `volume` | Number | No | Non-negative when present |
| `open_SAR`, `high_SAR`, `low_SAR`, `close_SAR` | Float | No | Context only |

SAR columns and volume are loaded and validated where relevant but are never used for modelling.

## Loading and validation

`btc_forecast.data.load_csv` performs these checks before any cleaning:

1. The file exists; an empty file is rejected.
2. The first column is treated as the date when its header is empty, starts with `Unnamed:`, or is
   `date`.
3. Every date parses; the first unparseable row is reported with its CSV row number.
4. `close_USD` exists.
5. All present price columns are numeric; the first offending value and row are reported.
6. Present price columns are positive.
7. `volume`, when present, is non-negative.

The loader returns the typed frame plus a `Dataset` with the source path, SHA-256 fingerprint,
record count and date range. `close` values are not scaled or transformed.

## Cleaning

`btc_forecast.preprocessing.clean_dataset` is deterministic:

1. Sort ascending by date (stable mergesort).
2. Remove exact duplicate rows and count them.
3. If the same date still appears more than once with different values, fail and list the
   conflicting dates.
4. Forward-fill missing values in present price columns and count the imputed values.
5. Exclude rows whose `close_USD` has no prior valid value (for example, a missing leading close).
   Future values are never used to fill earlier values.
6. Enforce OHLC consistency on rows where open, high, low and close are all present:
   `low <= min(open, close) <= max(open, close) <= high`.
7. Reject any remaining non-positive close.

Every action is recorded in a `PreprocessingSummary`:

| Field | Meaning |
|-------|---------|
| `source_count` | Rows read from the CSV |
| `accepted_count` | Rows retained |
| `rejected_count` | `source_count - accepted_count` |
| `duplicates_removed` | Exact duplicate rows removed |
| `missing_values_imputed` | Missing price values forward-filled |
| `rows_excluded_without_prior_value` | Rows dropped for lack of a prior close |
| `date_range` | First and last accepted dates |
| `actions` | Human-readable cleaning log |

For the provided dataset: 1000 source records, 1000 accepted, 0 duplicates, 0 imputations, range
`2018-05-07` to `2021-01-30`.

## Fingerprinting

The fingerprint is `sha256:` followed by the SHA-256 of the raw file bytes. It is stored in
`model.pkl`, `evaluation.json` and exposed by the CLI. The dashboard and `predict` compare the
current `dc.csv` fingerprint with the artifact fingerprint and refuse inference when they differ.
This prevents displaying a stale forecast after the dataset changes.

## Fixtures

`tests/fixtures/` contains small deterministic datasets so tests never depend on `dc.csv`:

| Fixture | Purpose |
|---------|---------|
| `dc_sample.csv` | 100 valid rows in descending order; supports an 80/20 split |
| `invalid_ohlc.csv` | One record violating the high/low bounds |
| `invalid_duplicate.csv` | Two conflicting rows for the same date |

## Data limitations

- Only USD closing prices are modelled; volume and OHLC context are not used as predictors.
- The dataset ends on `2021-01-30`. The application is not connected to live data, so forecasts are
  relative to that historical endpoint.
- The dataset is treated as authoritative; the loader does not reconcile it with any external
  source.
- Missing values are forward-filled, which assumes persistence of the last observed price. Such
  imputations are counted and surfaced in the insights text.
- Cryptocurrency prices are volatile and may contain regime changes that a univariate ARIMA model
  cannot anticipate.
