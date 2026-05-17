from __future__ import annotations

from typing import Any

import pandas as pd

from .schemas import ValidationResult


REQUIRED_COLUMNS = [
    "experiment_id",
    "model_name",
    "dataset",
    "prompt_version",
    "temperature",
    "accuracy",
    "precision",
    "recall",
    "f1",
    "avg_latency_ms",
    "cost_per_1k",
    "error_rate",
    "notes",
]

EVAL_CORE_COLUMNS = ["model_name"]
EVAL_METRIC_COLUMNS = [
    "accuracy",
    "precision",
    "recall",
    "f1",
    "avg_latency_ms",
    "cost_per_1k",
    "error_rate",
]


def validate_dataframe(dataframe: pd.DataFrame) -> ValidationResult:
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in dataframe.columns]
    warnings: list[str] = []

    if dataframe.empty:
        warnings.append("Input file contains no data rows.")

    numeric_type_summary: dict[str, str] = {}
    for column in EVAL_METRIC_COLUMNS + ["temperature"]:
        if column not in dataframe.columns:
            continue
        numeric_series = pd.to_numeric(dataframe[column], errors="coerce")
        invalid_count = int(numeric_series.isna().sum() - dataframe[column].isna().sum())
        if invalid_count > 0:
            warnings.append(f"Column '{column}' contains {invalid_count} non-numeric values.")
        numeric_type_summary[column] = str(numeric_series.dtype)

    null_summary: dict[str, float] = {}
    for column in dataframe.columns:
        null_ratio = float(dataframe[column].isna().mean())
        null_summary[str(column)] = round(null_ratio, 4)
        if null_ratio >= 0.3:
            warnings.append(f"Column '{column}' has high missing ratio: {null_ratio:.0%}.")

    duplicate_count = 0
    if "experiment_id" in dataframe.columns:
        duplicate_count = int(dataframe["experiment_id"].duplicated().sum())
        if duplicate_count > 0:
            warnings.append(f"Found {duplicate_count} duplicated experiment_id values.")

    available_metrics = [column for column in EVAL_METRIC_COLUMNS if column in dataframe.columns]
    quality_summary: dict[str, Any] = {
        "row_count": int(len(dataframe)),
        "column_count": int(len(dataframe.columns)),
        "null_ratio_by_column": null_summary,
        "duplicate_experiment_count": duplicate_count,
        "numeric_type_summary": numeric_type_summary,
        "available_metrics": available_metrics,
    }

    is_valid = "model_name" in dataframe.columns and len(available_metrics) >= 1
    return ValidationResult(
        is_valid=is_valid,
        missing_columns=missing_columns,
        warnings=warnings,
        quality_summary=quality_summary,
    )


def detect_eval_schema(columns: list[str]) -> dict[str, Any]:
    column_set = {str(column) for column in columns}
    matched_core = [column for column in EVAL_CORE_COLUMNS if column in column_set]
    matched_metrics = [column for column in EVAL_METRIC_COLUMNS if column in column_set]
    matched_total = [column for column in REQUIRED_COLUMNS if column in column_set]
    is_eval_like = bool(matched_core) and len(matched_metrics) >= 1
    return {
        "is_eval_like": is_eval_like,
        "matched_core": matched_core,
        "matched_metrics": matched_metrics,
        "matched_total": matched_total,
    }
