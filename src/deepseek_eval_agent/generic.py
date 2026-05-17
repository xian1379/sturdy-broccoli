from __future__ import annotations

import warnings
from typing import Any

import pandas as pd

from .aggregator import aggregate_metrics
from .detector import detect_table_theme
from .schemas import GenericSheetResult, LoadResult
from .validator import validate_dataframe


DIMENSION_HINTS = ["地市", "省分", "客户", "项目", "类型", "场景", "部门", "业务", "区域", "城市", "产品"]
NUMERIC_HINTS = ["金额", "数量", "次数", "收入", "成本", "率", "税", "余额", "回款", "未计收", "已计收", "应收"]
DATE_HINTS = ["日期", "时间", "月份", "期间", "年", "月"]
ID_HINTS = ["编号", "id", "code", "合同号", "项目号", "合同编号", "项目编号", "订单编号", "序号"]


def profile_table_structure(load_result: LoadResult) -> dict[str, Any]:
    dataframe = load_result.dataframe.copy()
    dataframe.columns = [str(column).strip() for column in dataframe.columns]

    low_value_columns: list[str] = []
    numeric_columns: list[str] = []
    date_columns: list[str] = []
    dimension_columns: list[str] = []
    id_columns: list[str] = []
    warnings_list: list[str] = []
    null_ratio_by_column: dict[str, float] = {}

    for column in dataframe.columns:
        series = dataframe[column]
        null_ratio = float(series.isna().mean())
        null_ratio_by_column[column] = round(null_ratio, 4)

        if _is_low_value_column(column, series, null_ratio):
            low_value_columns.append(column)
            if column.startswith("Unnamed"):
                warnings_list.append(f"Column '{column}' looks like an unnamed helper column.")
            elif null_ratio >= 0.95:
                warnings_list.append(f"Column '{column}' is nearly empty.")
            continue

        if _is_numeric_column(column, series):
            numeric_columns.append(column)
            if null_ratio >= 0.3:
                warnings_list.append(f"Numeric column '{column}' has high missing ratio: {null_ratio:.0%}.")
            continue

        if _is_date_column(column, series):
            date_columns.append(column)
            continue

        dimension_columns.append(column)
        if _is_id_like_column(column, series):
            id_columns.append(column)
            duplicate_count = int(series.astype(str).duplicated().sum())
            if duplicate_count > 0:
                warnings_list.append(f"Column '{column}' contains {duplicate_count} duplicated identifier values.")

    return {
        "row_count": int(len(dataframe)),
        "column_count": int(len(dataframe.columns)),
        "column_roles": {
            "dimension_columns": dimension_columns,
            "numeric_columns": numeric_columns,
            "date_columns": date_columns,
            "low_value_columns": low_value_columns,
            "id_columns": id_columns,
        },
        "null_ratio_by_column": null_ratio_by_column,
        "focus_dimension_columns": _pick_focus_columns(dimension_columns, DIMENSION_HINTS + ID_HINTS, fallback_limit=4),
        "focus_numeric_columns": _pick_focus_columns(numeric_columns, NUMERIC_HINTS, fallback_limit=4),
        "warnings": warnings_list,
    }


def run_generic_analysis(dataframe: pd.DataFrame, profile: dict[str, Any]) -> dict[str, Any]:
    numeric_columns = profile["column_roles"]["numeric_columns"]
    dimension_columns = profile["column_roles"]["dimension_columns"]

    numeric_summaries = {column: _summarize_numeric_column(dataframe[column]) for column in numeric_columns[:6]}
    dimension_summaries = {column: _summarize_dimension_column(dataframe[column]) for column in dimension_columns[:6]}
    grouped_summaries = _build_grouped_summaries(dataframe, dimension_columns, numeric_columns)
    anomaly_summary = _build_anomaly_summary(profile, grouped_summaries)

    return {
        "numeric_summaries": numeric_summaries,
        "dimension_summaries": dimension_summaries,
        "grouped_summaries": grouped_summaries,
        "anomaly_summary": anomaly_summary,
    }


def run_specialized_enhancement(load_result: LoadResult, profile: dict[str, Any], theme: str, analysis_config: dict[str, Any]) -> dict[str, Any]:
    dataframe = load_result.dataframe
    if theme == "eval":
        validation_result = validate_dataframe(dataframe)
        aggregation_result = aggregate_metrics(dataframe, analysis_config)
        return {
            "template": "eval_enhancement",
            "matched_theme": "eval",
            "validation": validation_result.quality_summary,
            "metric_summary": aggregation_result.metric_summary,
            "best_model": aggregation_result.best_model,
            "worst_model": aggregation_result.worst_model,
            "outliers": aggregation_result.outliers,
            "tradeoff_summary": aggregation_result.tradeoff_summary,
        }

    numeric_columns = profile["column_roles"]["numeric_columns"]
    dimension_columns = profile["column_roles"]["dimension_columns"]

    if theme == "business":
        return {
            "template": "business_enhancement",
            "matched_theme": "business",
            "top_amount_columns": numeric_columns[:3],
            "top_dimension_columns": dimension_columns[:3],
            "business_signals": _build_business_signals(dataframe, profile),
        }

    if theme == "financial":
        return {
            "template": "financial_enhancement",
            "matched_theme": "financial",
            "top_amount_columns": numeric_columns[:4],
            "financial_signals": _build_financial_signals(dataframe, profile),
        }

    return {
        "template": "generic",
        "matched_theme": "generic",
        "message": "No specialized template matched strongly; using generic structured-table analysis.",
    }


def build_universal_sheet_result(load_result: LoadResult, analysis_config: dict[str, Any]) -> GenericSheetResult:
    profile = profile_table_structure(load_result)
    theme_info = detect_table_theme(load_result.detected_columns)
    aggregation = run_generic_analysis(load_result.dataframe, profile)
    specialized_insights = run_specialized_enhancement(load_result, profile, str(theme_info["table_theme"]), analysis_config)
    quality_summary = {
        "row_count": profile["row_count"],
        "column_count": profile["column_count"],
        "null_ratio_by_column": profile["null_ratio_by_column"],
        "warning_count": len(profile["warnings"]),
        "warnings": profile["warnings"],
    }
    return GenericSheetResult(
        sheet_name=load_result.sheet_name or "Sheet1",
        table_theme=str(theme_info["table_theme"]),
        detected_columns=load_result.detected_columns,
        column_roles=profile["column_roles"],
        quality_summary=quality_summary,
        profile={key: value for key, value in profile.items() if key != "warnings"},
        aggregation=aggregation,
        specialized_insights=specialized_insights,
        warnings=profile["warnings"],
    )


def summarize_workbook(sheet_results: list[GenericSheetResult]) -> dict[str, Any]:
    total_rows = sum(sheet.profile["row_count"] for sheet in sheet_results)
    total_columns = sum(sheet.profile["column_count"] for sheet in sheet_results)
    warning_counts = {sheet.sheet_name: len(sheet.warnings) for sheet in sheet_results}
    focus_sheet = max(sheet_results, key=lambda item: item.profile["row_count"], default=None)
    best_quality_sheet = min(sheet_results, key=lambda item: len(item.warnings), default=None)
    worst_quality_sheet = max(sheet_results, key=lambda item: len(item.warnings), default=None)
    theme_counts: dict[str, int] = {}
    for sheet in sheet_results:
        theme_counts[sheet.table_theme] = theme_counts.get(sheet.table_theme, 0) + 1

    return {
        "sheet_count": len(sheet_results),
        "total_rows": total_rows,
        "total_columns": total_columns,
        "theme_counts": theme_counts,
        "sheet_overview": [
            {
                "sheet_name": sheet.sheet_name,
                "table_theme": sheet.table_theme,
                "row_count": sheet.profile["row_count"],
                "column_count": sheet.profile["column_count"],
                "warning_count": len(sheet.warnings),
                "focus_numeric_columns": sheet.profile["focus_numeric_columns"],
                "focus_dimension_columns": sheet.profile["focus_dimension_columns"],
            }
            for sheet in sheet_results
        ],
        "best_quality_sheet": best_quality_sheet.sheet_name if best_quality_sheet else None,
        "worst_quality_sheet": worst_quality_sheet.sheet_name if worst_quality_sheet else None,
        "focus_sheet": focus_sheet.sheet_name if focus_sheet else None,
        "warnings_count_by_sheet": warning_counts,
    }


def _build_business_signals(dataframe: pd.DataFrame, profile: dict[str, Any]) -> dict[str, Any]:
    grouped = _build_grouped_summaries(
        dataframe,
        profile["column_roles"]["dimension_columns"],
        profile["column_roles"]["numeric_columns"],
    )
    return {
        "focus_dimensions": profile["focus_dimension_columns"],
        "focus_numeric_columns": profile["focus_numeric_columns"],
        "top_group_summaries": grouped[:4],
    }


def _build_financial_signals(dataframe: pd.DataFrame, profile: dict[str, Any]) -> dict[str, Any]:
    numeric_summaries = run_generic_analysis(dataframe, profile)["numeric_summaries"]
    sorted_by_sum = sorted(
        [
            {"column": column, "sum": summary["sum"], "max": summary["max"]}
            for column, summary in numeric_summaries.items()
            if summary["sum"] is not None
        ],
        key=lambda item: item["sum"],
        reverse=True,
    )
    return {
        "largest_amount_columns": sorted_by_sum[:4],
        "focus_numeric_columns": profile["focus_numeric_columns"],
    }


def _build_anomaly_summary(profile: dict[str, Any], grouped_summaries: list[dict[str, Any]]) -> dict[str, Any]:
    high_missing_columns = [
        column
        for column, ratio in profile["null_ratio_by_column"].items()
        if ratio >= 0.3
    ]
    return {
        "high_missing_columns": high_missing_columns,
        "low_value_columns": profile["column_roles"]["low_value_columns"],
        "grouped_summary_count": len(grouped_summaries),
        "warning_count": len(profile["warnings"]),
    }


def _is_low_value_column(column: str, series: pd.Series, null_ratio: float) -> bool:
    if column.startswith("Unnamed"):
        return True
    if null_ratio >= 0.95:
        return True
    return int(series.notna().sum()) <= 1


def _is_numeric_column(column: str, series: pd.Series) -> bool:
    if any(hint in column for hint in NUMERIC_HINTS):
        return True
    non_null = series.dropna()
    if non_null.empty:
        return False
    coerced = pd.to_numeric(non_null, errors="coerce")
    success_ratio = float(coerced.notna().mean())
    return success_ratio >= 0.8 and coerced.notna().sum() >= 2


def _is_date_column(column: str, series: pd.Series) -> bool:
    if any(hint in column for hint in DATE_HINTS):
        return True
    non_null = series.dropna()
    if non_null.empty:
        return False
    sample_text = " ".join(non_null.astype(str).head(5).tolist())
    if not any(token in sample_text for token in ["-", "/", "年", "月", ":"]):
        return False
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        parsed = pd.to_datetime(non_null, errors="coerce")
    return float(parsed.notna().mean()) >= 0.8


def _is_id_like_column(column: str, series: pd.Series) -> bool:
    lowered = column.lower()
    if any(hint in lowered for hint in ["id", "code"]):
        return True
    if any(hint in column for hint in ID_HINTS):
        return True
    non_null = series.dropna()
    if non_null.empty:
        return False
    unique_ratio = float(non_null.astype(str).nunique() / max(len(non_null), 1))
    return unique_ratio >= 0.9


def _summarize_numeric_column(series: pd.Series) -> dict[str, Any]:
    numeric_series = pd.to_numeric(series, errors="coerce")
    return {
        "sum": _round_or_none(numeric_series.sum()),
        "mean": _round_or_none(numeric_series.mean()),
        "median": _round_or_none(numeric_series.median()),
        "min": _round_or_none(numeric_series.min()),
        "max": _round_or_none(numeric_series.max()),
        "missing_ratio": round(float(numeric_series.isna().mean()), 4),
    }


def _summarize_dimension_column(series: pd.Series) -> dict[str, Any]:
    normalized = series.dropna().astype(str)
    top_values = normalized.value_counts().head(5)
    return {
        "unique_count": int(normalized.nunique()),
        "top_values": top_values.to_dict(),
        "missing_ratio": round(float(series.isna().mean()), 4),
    }


def _build_grouped_summaries(dataframe: pd.DataFrame, dimension_columns: list[str], numeric_columns: list[str]) -> list[dict[str, Any]]:
    grouped_summaries: list[dict[str, Any]] = []
    selected_dimensions = _pick_focus_columns(dimension_columns, DIMENSION_HINTS + ID_HINTS, fallback_limit=2)
    selected_numerics = _pick_focus_columns(numeric_columns, NUMERIC_HINTS, fallback_limit=2)

    for dimension in selected_dimensions:
        for numeric in selected_numerics:
            frame = dataframe[[dimension, numeric]].copy()
            frame[numeric] = pd.to_numeric(frame[numeric], errors="coerce")
            frame = frame.dropna(subset=[dimension, numeric])
            if frame.empty:
                continue
            grouped = frame.groupby(dimension)[numeric].sum().sort_values(ascending=False).head(5)
            grouped_summaries.append(
                {
                    "dimension": dimension,
                    "numeric": numeric,
                    "top_groups": {str(key): _round_or_none(value) for key, value in grouped.to_dict().items()},
                }
            )
    return grouped_summaries[:8]


def _pick_focus_columns(columns: list[str], hints: list[str], fallback_limit: int) -> list[str]:
    hinted = [column for column in columns if any(hint.lower() in column.lower() for hint in hints)]
    if hinted:
        return hinted[:fallback_limit]
    return columns[:fallback_limit]


def _round_or_none(value: Any) -> float | None:
    if pd.isna(value):
        return None
    return round(float(value), 4)
