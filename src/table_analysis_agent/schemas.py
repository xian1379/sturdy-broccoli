from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class FileInfo:
    path: str
    file_type: str
    row_count: int
    column_count: int
    file_size_bytes: int


@dataclass
class LoadResult:
    dataframe: Any
    file_info: FileInfo
    detected_columns: list[str]
    sheet_name: str | None = None


@dataclass
class WorkbookLoadResult:
    source_name: str
    file_type: str
    file_size_bytes: int
    sheets: list[LoadResult]


@dataclass
class ValidationResult:
    is_valid: bool
    missing_columns: list[str]
    warnings: list[str]
    quality_summary: dict[str, Any]


@dataclass
class AggregationResult:
    metric_summary: dict[str, Any]
    best_model: dict[str, Any]
    worst_model: dict[str, Any]
    outliers: list[dict[str, Any]]
    tradeoff_summary: dict[str, Any]


@dataclass
class AnalysisResult:
    llm_insights: str
    recommendations: list[str]
    risk_notes: list[str]
    used_llm: bool
    error_message: str | None = None


@dataclass
class GenericSheetResult:
    sheet_name: str
    table_theme: str
    detected_columns: list[str]
    column_roles: dict[str, list[str]]
    quality_summary: dict[str, Any]
    profile: dict[str, Any]
    aggregation: dict[str, Any]
    specialized_insights: dict[str, Any]
    warnings: list[str]


@dataclass
class AppConfig:
    env: dict[str, Any]
    report: dict[str, Any]
    analysis: dict[str, Any]
    llm: dict[str, Any]


@dataclass
class PipelineResult:
    analysis_mode: str
    table_theme: str
    input_path: Path
    report_path: Path
    mode_reason: str = ""
    workbook_summary: dict[str, Any] = field(default_factory=dict)
    sheet_results: list[GenericSheetResult] = field(default_factory=list)
    quality_summary: dict[str, Any] = field(default_factory=dict)
    specialized_insights: dict[str, Any] = field(default_factory=dict)
    load: LoadResult | None = None
    validation: ValidationResult | None = None
    aggregation: AggregationResult | None = None
    analysis: AnalysisResult | None = None
    artifacts: dict[str, Path] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["input_path"] = str(self.input_path)
        payload["report_path"] = str(self.report_path)
        payload["artifacts"] = {key: str(value) for key, value in self.artifacts.items()}
        return payload
