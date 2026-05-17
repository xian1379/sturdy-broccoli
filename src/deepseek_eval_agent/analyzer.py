from __future__ import annotations

import json
from typing import Any

import requests

from .schemas import AnalysisResult, AppConfig, GenericSheetResult


def analyze_universal_with_llm(
    workbook_summary: dict[str, Any],
    sheet_results: list[GenericSheetResult],
    config: AppConfig,
) -> AnalysisResult:
    messages = build_universal_analysis_prompt(workbook_summary, sheet_results, config)
    return _call_llm(messages, config, fallback_universal_analysis)


def build_universal_analysis_prompt(
    workbook_summary: dict[str, Any],
    sheet_results: list[GenericSheetResult],
    config: AppConfig,
) -> list[dict[str, str]]:
    system_prompt = (
        "You are an AI assistant for universal spreadsheet analysis. "
        "Use only the provided structured summaries. "
        "Respond in Chinese. Focus on stable conclusions, anomalies, and actionable recommendations. "
        "If a sheet is evaluation-themed, mention model comparison. "
        "If a sheet is business or financial-themed, mention amount concentration, receivable risks, or data quality issues when supported by the data. "
        "Output valid JSON with keys: llm_insights, recommendations, risk_notes."
    )
    user_payload = {
        "report_language": config.report.get("language", "zh"),
        "analysis_mode": "universal",
        "workbook_summary": workbook_summary,
        "sheet_results": [
            {
                "sheet_name": sheet.sheet_name,
                "table_theme": sheet.table_theme,
                "column_roles": sheet.column_roles,
                "quality_summary": sheet.quality_summary,
                "aggregation": sheet.aggregation,
                "specialized_insights": sheet.specialized_insights,
                "warnings": sheet.warnings,
            }
            for sheet in sheet_results
        ],
    }
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False, indent=2)},
    ]


def _call_llm(
    messages: list[dict[str, str]],
    config: AppConfig,
    fallback_factory: Any,
) -> AnalysisResult:
    if not config.env.get("api_key"):
        return fallback_factory("No API key configured. Generated statistics-only report.")

    url = f"{config.env['base_url'].rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.env['api_key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config.env["model"],
        "temperature": config.llm.get("temperature", 0.2),
        "messages": messages,
        "response_format": {"type": "json_object"},
    }

    last_error = None
    retries = max(1, int(config.env.get("max_retries", 1)))
    for _ in range(retries):
        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=int(config.env.get("timeout", 60)),
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            return AnalysisResult(
                llm_insights=str(parsed.get("llm_insights", "")).strip(),
                recommendations=_normalize_list_field(parsed.get("recommendations", [])),
                risk_notes=_normalize_list_field(parsed.get("risk_notes", [])),
                used_llm=True,
            )
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)

    return fallback_factory(f"LLM call failed: {last_error}")


def fallback_universal_analysis(reason: str) -> AnalysisResult:
    return AnalysisResult(
        llm_insights="未使用 LLM 分析，当前报告基于通用表格统计结果生成。",
        recommendations=[
            "优先检查高缺失字段、低价值列和重复编号列。",
            "围绕重点维度与金额/数量列做进一步分组复盘。",
            "若存在金额或回款字段，优先核查大额未计收、异常波动和单位不一致问题。",
        ],
        risk_notes=[reason],
        used_llm=False,
        error_message=reason,
    )


def _normalize_list_field(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        return [line.strip("- ").strip() for line in stripped.splitlines() if line.strip()]
    return [str(value).strip()] if str(value).strip() else []
