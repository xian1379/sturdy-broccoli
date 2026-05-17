from __future__ import annotations

from pathlib import Path

from .analyzer import analyze_universal_with_llm
from .config import build_app_config
from .detector import detect_analysis_mode
from .generic import build_universal_sheet_result, summarize_workbook
from .loader import load_workbook_file
from .reporter import render_universal_report, write_docx_summary, write_report
from .schemas import PipelineResult, WorkbookLoadResult


def run_pipeline_from_path(project_root: Path, input_path: Path, output_path: Path) -> PipelineResult:
    workbook = load_workbook_file(input_path)
    return run_pipeline_from_workbook(project_root, input_path, workbook, output_path)


def run_pipeline_from_workbook(
    project_root: Path,
    input_path: Path,
    workbook: WorkbookLoadResult,
    output_path: Path,
) -> PipelineResult:
    app_config = build_app_config(project_root)
    mode_info = detect_analysis_mode(workbook)

    sheet_results = [
        build_universal_sheet_result(sheet, app_config.analysis)
        for sheet in workbook.sheets
        if sheet.file_info.row_count > 0 or sheet.file_info.column_count > 0
    ]
    workbook_summary = summarize_workbook(sheet_results)
    analysis_result = analyze_universal_with_llm(workbook_summary, sheet_results, app_config)
    report_content = render_universal_report(
        input_path=input_path,
        table_theme=str(mode_info["table_theme"]),
        workbook_summary=workbook_summary,
        sheet_results=sheet_results,
        analysis=analysis_result,
        mode_reason=str(mode_info["reason"]),
    )
    report_path = write_report(report_content, output_path)
    docx_path = output_path.with_suffix(".docx")
    write_docx_summary(
        input_path=input_path,
        table_theme=str(mode_info["table_theme"]),
        workbook_summary=workbook_summary,
        sheet_results=sheet_results,
        analysis=analysis_result,
        output_path=docx_path,
    )

    quality_summary = {
        sheet.sheet_name: sheet.quality_summary
        for sheet in sheet_results
    }
    specialized_insights = {
        sheet.sheet_name: sheet.specialized_insights
        for sheet in sheet_results
    }

    return PipelineResult(
        analysis_mode="universal",
        table_theme=str(mode_info["table_theme"]),
        input_path=input_path,
        report_path=report_path,
        mode_reason=str(mode_info["reason"]),
        workbook_summary=workbook_summary,
        sheet_results=sheet_results,
        quality_summary=quality_summary,
        specialized_insights=specialized_insights,
        analysis=analysis_result,
        artifacts={"report": report_path, "document": docx_path},
    )
