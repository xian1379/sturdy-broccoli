from __future__ import annotations

from typing import Any

import pandas as pd

from .schemas import AggregationResult


def _coerce_numeric_columns(dataframe: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    result = dataframe.copy()
    for column in columns:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")
    return result


def aggregate_metrics(dataframe: pd.DataFrame, config: dict[str, Any]) -> AggregationResult:
    candidate_metrics = ["accuracy", "precision", "recall", "f1", "avg_latency_ms", "cost_per_1k", "error_rate"]
    available_metrics = [column for column in candidate_metrics if column in dataframe.columns]
    df = _coerce_numeric_columns(dataframe, available_metrics + ["temperature"])

    if "model_name" not in df.columns:
        raise ValueError("Evaluation mode requires a 'model_name' column.")
    if not available_metrics:
        raise ValueError("Evaluation mode requires at least one metric column.")

    primary_metric = config.get("primary_metric", "accuracy")
    latency_metric = config.get("latency_metric", "avg_latency_ms")
    cost_metric = config.get("cost_metric", "cost_per_1k")
    outlier_threshold = float(config.get("outlier_zscore_threshold", 2.0))

    sort_metric = primary_metric if primary_metric in available_metrics else available_metrics[0]
    grouped = (
        df.groupby("model_name", dropna=False)[available_metrics]
        .mean(numeric_only=True)
        .round(4)
        .sort_values(by=sort_metric, ascending=False)
    )

    metric_summary = {
        "models": grouped.reset_index().to_dict(orient="records"),
        "overall_rows": int(len(df)),
        "model_count": int(grouped.shape[0]),
        "primary_metric": sort_metric,
        "available_metrics": available_metrics,
    }

    best_model = {}
    worst_model = {}
    if not grouped.empty:
        best_name = grouped.index[0]
        worst_name = grouped.index[-1]
        best_model = {"model_name": best_name, **grouped.iloc[0].to_dict()}
        worst_model = {"model_name": worst_name, **grouped.iloc[-1].to_dict()}

    outliers: list[dict[str, Any]] = []
    if sort_metric in df.columns and df[sort_metric].notna().sum() >= 2:
        mean_value = float(df[sort_metric].mean())
        std_value = float(df[sort_metric].std(ddof=0))
        if std_value > 0:
            zscores = ((df[sort_metric] - mean_value) / std_value).abs()
            outlier_columns = ["experiment_id", "model_name", sort_metric]
            for optional_column in [latency_metric, cost_metric, "error_rate"]:
                if optional_column in df.columns and optional_column not in outlier_columns:
                    outlier_columns.append(optional_column)
            candidates = df.loc[zscores >= outlier_threshold, outlier_columns]
            outliers = candidates.fillna("N/A").to_dict(orient="records")

    best_latency_name = None
    best_cost_name = None
    if not grouped.empty and latency_metric in grouped.columns:
        best_latency_name = str(grouped[latency_metric].idxmin())
    if not grouped.empty and cost_metric in grouped.columns:
        best_cost_name = str(grouped[cost_metric].idxmin())

    tradeoff_summary = {
        "best_primary_model": best_model.get("model_name"),
        "lowest_latency_model": best_latency_name,
        "lowest_cost_model": best_cost_name,
        "tradeoff_comment": _build_tradeoff_comment(best_model, best_latency_name, best_cost_name),
    }

    return AggregationResult(
        metric_summary=metric_summary,
        best_model=best_model,
        worst_model=worst_model,
        outliers=outliers,
        tradeoff_summary=tradeoff_summary,
    )


def _build_tradeoff_comment(best_model: dict[str, Any], best_latency_name: str | None, best_cost_name: str | None) -> str:
    best_name = best_model.get("model_name")
    if not best_name:
        return "No valid model comparison available."
    if best_name == best_latency_name == best_cost_name:
        return f"{best_name} is strongest on quality and also leads on efficiency."
    if best_name == best_latency_name:
        return f"{best_name} balances top quality with the best latency."
    if best_name == best_cost_name:
        return f"{best_name} combines top quality with the lowest cost."
    return f"{best_name} leads on the primary metric, while latency and cost are led by other models."
