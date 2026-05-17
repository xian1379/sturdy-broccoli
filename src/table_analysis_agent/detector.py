from __future__ import annotations

from collections import Counter
from typing import Any

from .schemas import WorkbookLoadResult
from .validator import detect_eval_schema


BUSINESS_HINTS = ["地市", "省分", "客户", "项目", "合同", "场景", "类型", "回款", "未计收", "已计收"]
FINANCIAL_HINTS = ["金额", "税率", "成本", "收入", "回款", "未计收", "已计收", "余额", "应收"]


def detect_analysis_mode(workbook: WorkbookLoadResult) -> dict[str, Any]:
    sheet_detections = []
    for sheet in workbook.sheets:
        detection = detect_table_theme(sheet.detected_columns)
        sheet_detections.append(
            {
                "sheet_name": sheet.sheet_name or "Sheet1",
                "table_theme": detection["table_theme"],
                "reason": detection["reason"],
                "matched_columns": detection["matched_columns"],
            }
        )

    themes = [item["table_theme"] for item in sheet_detections] or ["generic"]
    counter = Counter(themes)
    dominant_theme = _pick_dominant_theme(counter)
    sheet_count = len(sheet_detections)

    reason = f"Universal analysis enabled for {sheet_count} sheet(s); dominant theme is {dominant_theme}."
    return {
        "mode": "universal",
        "reason": reason,
        "table_theme": dominant_theme,
        "sheet_count": sheet_count,
        "sheet_detections": sheet_detections,
    }


def detect_table_theme(columns: list[str]) -> dict[str, Any]:
    normalized = [str(column) for column in columns]
    eval_check = detect_eval_schema(normalized)
    if eval_check["is_eval_like"]:
        return {
            "table_theme": "eval",
            "reason": "Detected model_name with one or more evaluation metric columns.",
            "matched_columns": eval_check["matched_total"],
        }

    business_matches = [column for column in normalized if any(hint in column for hint in BUSINESS_HINTS)]
    financial_matches = [column for column in normalized if any(hint in column for hint in FINANCIAL_HINTS)]

    if len(business_matches) >= 2 and len(financial_matches) >= 1:
        return {
            "table_theme": "business",
            "reason": "Detected project/customer/contract dimensions together with amount-like columns.",
            "matched_columns": sorted(set(business_matches + financial_matches)),
        }

    if len(financial_matches) >= 2:
        return {
            "table_theme": "financial",
            "reason": "Detected multiple amount-like or receivable-like columns.",
            "matched_columns": financial_matches,
        }

    return {
        "table_theme": "generic",
        "reason": "No specialized theme matched strongly; using generic structured-table analysis.",
        "matched_columns": business_matches or financial_matches,
    }


def _pick_dominant_theme(counter: Counter[str]) -> str:
    for preferred in ["business", "financial", "eval", "generic"]:
        if counter.get(preferred):
            return preferred
    return "generic"
