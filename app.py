"""Streamlit entry point for the Bitcoin next-day forecast dashboard."""

from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from btc_forecast.config import (
    DEFAULT_ARTIFACTS_DIR,
    DEFAULT_DATA_PATH,
    DISCLAIMER,
    MODEL_ARTIFACT_NAME,
)
from btc_forecast.dashboard.data import (
    DashboardData,
    DashboardView,
    load_dashboard_data,
    load_dashboard_view,
)
from btc_forecast.data import DataError
from btc_forecast.persistence import ArtifactError, load_model_artifact

st.set_page_config(
    page_title="Bitcoin Next-Day Forecast",
    page_icon="₿",
    layout="wide",
)


@st.cache_data(show_spinner=False)
def cached_data(data_path: str) -> DashboardData:
    """Cache the cleaned dataset and its fingerprint."""

    return load_dashboard_data(data_path)


@st.cache_resource(show_spinner=False)
def cached_model(model_path: str, fingerprint: str) -> tuple[str, object]:
    """Cache the persisted model as a shared resource.

    Returns ``("ok", artifact)``, ``("missing", "")`` or ``("invalid", reason)``.
    """

    path = Path(model_path)
    if not path.is_file():
        return ("missing", "")
    try:
        return ("ok", load_model_artifact(path, fingerprint))
    except ArtifactError as exc:
        return ("invalid", str(exc))


def price_forecast_chart(history: pd.DataFrame, forecast: object) -> alt.LayerChart:
    """Historical close line with a labeled next-day forecast marker."""

    history_frame = history.copy()
    history_frame["date"] = pd.to_datetime(history_frame["date"])

    forecast_date = pd.to_datetime(forecast.target_date)
    forecast_frame = pd.DataFrame(
        {
            "date": [forecast_date],
            "close_USD": [forecast.predicted_close],
            "label": [f"Forecast {forecast.target_date}"],
        }
    )

    base = alt.Chart(history_frame).encode(
        x=alt.X("date:T", title="Date"),
        y=alt.Y("close_USD:Q", title="USD closing price", scale=alt.Scale(zero=False)),
    )
    line = base.mark_line(color="#1f77b4").encode(
        tooltip=[
            alt.Tooltip("date:T", title="Date"),
            alt.Tooltip("close_USD:Q", title="Actual close", format=",.2f"),
        ]
    )
    marker_rule = (
        alt.Chart(forecast_frame)
        .mark_rule(color="#d62728", strokeDash=[4, 4])
        .encode(x="date:T")
    )
    marker = (
        alt.Chart(forecast_frame)
        .mark_point(size=160, filled=True, shape="diamond", color="#d62728")
        .encode(
            x="date:T",
            y="close_USD:Q",
            tooltip=[
                alt.Tooltip("date:T", title="Date"),
                alt.Tooltip("close_USD:Q", title="Forecast", format=",.2f"),
                alt.Tooltip("label:N", title="Marker"),
            ],
        )
    )
    label = (
        alt.Chart(forecast_frame)
        .mark_text(dy=-14, color="#d62728", fontWeight="bold")
        .encode(x="date:T", y="close_USD:Q", text="label:N")
    )
    return (
        (line + marker_rule + marker + label)
        .properties(
            height=380,
            title="USD closing price history with the labeled next-day forecast marker",
        )
        .interactive()
    )


def backtest_chart(predictions: pd.DataFrame) -> alt.LayerChart:
    """Validation actuals versus ARIMA and naive baseline predictions."""

    frame = predictions.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    melted = frame.melt(
        id_vars="date",
        value_vars=["actual_close", "model_prediction", "baseline_prediction"],
        var_name="Series",
        value_name="Price",
    )
    labels = {
        "actual_close": "Actual",
        "model_prediction": "ARIMA",
        "baseline_prediction": "Naive baseline",
    }
    melted["Series"] = melted["Series"].map(labels)

    chart = (
        alt.Chart(melted)
        .mark_line()
        .encode(
            x=alt.X("date:T", title="Validation date"),
            y=alt.Y("Price:Q", title="USD closing price", scale=alt.Scale(zero=False)),
            color=alt.Color(
                "Series:N",
                title="Series",
                scale=alt.Scale(
                    domain=["Actual", "ARIMA", "Naive baseline"],
                    range=["#1f77b4", "#d62728", "#2ca02c"],
                ),
            ),
            strokeDash=alt.StrokeDash(
                "Series:N",
                title="Series",
                scale=alt.Scale(
                    domain=["Actual", "ARIMA", "Naive baseline"],
                    range=[[1, 0], [6, 3], [2, 2]],
                ),
            ),
            tooltip=[
                alt.Tooltip("date:T", title="Date"),
                alt.Tooltip("Series:N", title="Series"),
                alt.Tooltip("Price:Q", title="Price", format=",.2f"),
            ],
        )
        .properties(
            height=340,
            title="Validation period: actual close versus ARIMA and naive baseline",
        )
        .interactive()
    )
    return chart


def render_failure(view: DashboardView, status: str) -> None:
    """Render actionable empty or invalid states without fabricated values."""

    st.error(view.message)
    if status == "missing_artifacts":
        st.code(
            "python -m btc_forecast.cli train --data dc.csv --artifacts artifacts",
            language="bash",
        )
        st.caption("Run the command above, then press Reload data in the sidebar.")
    elif status == "invalid_artifacts":
        st.caption(
            "Re-run training to regenerate artifacts from the current dc.csv, "
            "then press Reload data in the sidebar."
        )
    st.stop()


def render_header(view: DashboardView) -> None:
    """Render the persistent header, including target, horizon and disclaimer."""

    st.title("Bitcoin Next-Day Forecast")
    st.caption(
        "Target: close_USD (USD closing price) | Horizon: 1 day after the last "
        "observed date | Read-only decision support; the page never trains a model."
    )
    st.warning(DISCLAIMER)

    metadata = view.metadata
    forecast = view.forecast
    if forecast is None:
        return

    order = metadata.get("order", [])
    order_text = (
        f"ARIMA({order[0]}, {order[1]}, {order[2]})" if len(order) == 3 else "ARIMA"
    )
    data_range = metadata.get("data_range", [])
    range_text = (
        f"{data_range[0]} to {data_range[1]}" if len(data_range) == 2 else "N/A"
    )
    header = st.columns(4)
    header[0].metric("Model", order_text)
    header[1].metric("Data range", range_text)
    header[2].metric("Last observed", metadata.get("last_observed_date", "N/A"))
    header[3].metric("Artifact created", str(metadata.get("created_at", "unknown")))
    st.caption(
        f"Dataset fingerprint: {str(metadata.get('dataset_fingerprint', ''))[:23]} | "
        f"Artifact version: {metadata.get('artifact_version', 'N/A')}"
    )


def render_body(view: DashboardView) -> None:
    """Render the forecast, charts, metrics, insights and footer."""

    forecast = view.forecast
    metadata = view.metadata
    if forecast is None or view.history is None:
        st.error("The dashboard view is incomplete. Re-run training and reload.")
        st.stop()

    st.subheader("Forecast summary")
    summary = st.columns(4)
    summary[0].metric("Target date", forecast.target_date)
    summary[1].metric("Forecast close", f"USD {forecast.predicted_close:,.2f}")
    summary[2].metric("Last observed close", f"USD {forecast.last_observed_close:,.2f}")
    summary[3].metric(
        "Change",
        f"{forecast.percentage_change * 100:+.2f}%",
        delta=forecast.direction.capitalize(),
    )
    st.caption(
        f"Forecast generated by this dashboard at {forecast.generated_at}. "
        "Values are estimates, not guarantees."
    )

    st.subheader("Historical closing price and forecast")
    st.altair_chart(price_forecast_chart(view.history, forecast), width="stretch")

    st.subheader("Validation metrics")
    metrics = view.metrics
    if metrics is None:
        st.info("Validation metrics are not available in the current artifacts.")
    else:
        rows = []
        for label, section in (
            ("ARIMA", "model_metrics"),
            ("Naive Last Value", "baseline_metrics"),
        ):
            values = metrics[section]
            r2 = values["r2"]
            rows.append(
                {
                    "Model": label,
                    "MAE": f"{float(values['mae']):.6f}",
                    "MSE": f"{float(values['mse']):.6f}",
                    "RMSE": f"{float(values['rmse']):.6f}",
                    "R²": "N/A" if r2 is None else f"{float(r2):.6f}",
                }
            )
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        validation_range = metadata.get("validation_range", [])
        period = (
            f"{validation_range[0]} to {validation_range[1]}"
            if len(validation_range) == 2
            else "the validation period"
        )
        st.caption(
            f"One-step-ahead out-of-sample results over {period}; "
            f"{metrics['model_metrics']['observation_count']} observations. "
            "These metrics do not guarantee future accuracy."
        )
        if metrics.get("outperforms_baseline_rmse"):
            st.write(
                "ARIMA achieved a lower validation RMSE than the naive last-value "
                "baseline."
            )
        else:
            st.write(
                "The naive last-value baseline achieved a lower validation RMSE "
                "than ARIMA."
            )

    st.subheader("Validation backtest")
    if view.validation_predictions is None:
        st.info(
            "Validation predictions are not available. Re-run training to "
            "regenerate validation_predictions.csv."
        )
    else:
        st.altair_chart(backtest_chart(view.validation_predictions), width="stretch")

    st.subheader("Insights")
    insights = view.insights
    if insights is None:
        st.info("Insights are not available in the current artifacts.")
    else:
        st.markdown(
            f"**Forecast direction:** {insights.direction.capitalize()} "
            f"({insights.percentage_change * 100:+.2f}% versus the last close)."
        )
        st.markdown(f"**Model versus baseline:** {insights.model_vs_baseline}")
        st.markdown(f"**Data quality:** {insights.data_quality}")
        st.markdown("**Known limitations:**")
        for limitation in insights.limitations:
            st.markdown(f"- {limitation}")
        st.warning(insights.disclaimer)

    st.divider()
    st.caption(
        f"Artifact version: {metadata.get('artifact_version', 'N/A')} | "
        f"Artifact created: {metadata.get('created_at', 'unknown')} | "
        "Reproduce: python -m btc_forecast.cli train --data dc.csv "
        "--artifacts artifacts"
    )
    st.caption(DISCLAIMER)


def main() -> None:
    with st.sidebar:
        st.header("Data")
        if st.button("Reload data"):
            cached_data.clear()
            cached_model.clear()
            st.rerun()
        st.caption(
            "Artifacts are generated locally by the training command. "
            "The dashboard is read-only and never trains a model."
        )

    with st.spinner("Loading dataset and model artifacts..."):
        try:
            data = cached_data(str(DEFAULT_DATA_PATH))
        except DataError as exc:
            view = DashboardView(status="data_error", message=str(exc))
        except Exception as exc:  # noqa: BLE001 - surface read failures as data_error
            view = DashboardView(
                status="data_error",
                message=f"Could not read the source dataset: {exc}",
            )
        else:
            model_path = Path(DEFAULT_ARTIFACTS_DIR) / MODEL_ARTIFACT_NAME
            status, payload = cached_model(str(model_path), data.fingerprint)
            if status == "invalid":
                view = DashboardView(
                    status="invalid_artifacts",
                    message=str(payload),
                    history=data.history,
                )
            elif status == "ok":
                view = load_dashboard_view(
                    data=data,
                    artifact=payload,  # type: ignore[arg-type]
                )
            else:
                view = load_dashboard_view(data=data)

    render_header(view)

    if view.status in {"missing_artifacts", "invalid_artifacts", "data_error"}:
        render_failure(view, view.status)

    if view.status == "partial_artifacts":
        st.info(view.message)

    render_body(view)


if __name__ == "__main__":
    main()
