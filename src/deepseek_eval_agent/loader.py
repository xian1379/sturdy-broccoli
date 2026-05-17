from __future__ import annotations

import csv
from io import BytesIO, StringIO
from pathlib import Path

import pandas as pd

from .schemas import FileInfo, LoadResult, WorkbookLoadResult


SUPPORTED_EXTENSIONS = {".csv", ".xlsx"}


def load_workbook_file(input_path: Path) -> WorkbookLoadResult:
    suffix = input_path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {suffix}")

    if suffix == ".csv":
        dataframe = pd.read_csv(input_path)
        sheets = [
            build_load_result_from_dataframe(
                dataframe=dataframe,
                source_name=str(input_path.resolve()),
                file_type="csv",
                file_size_bytes=input_path.stat().st_size,
                sheet_name=input_path.stem,
            )
        ]
    else:
        sheets = _load_excel_sheets_from_bytes(
            payload=input_path.read_bytes(),
            source_name=str(input_path.resolve()),
            file_size_bytes=input_path.stat().st_size,
        )

    return WorkbookLoadResult(
        source_name=str(input_path.resolve()),
        file_type=suffix.lstrip("."),
        file_size_bytes=input_path.stat().st_size,
        sheets=sheets,
    )


def load_uploaded_workbook(file_name: str, payload: bytes) -> WorkbookLoadResult:
    suffix = Path(file_name).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {suffix}")

    if suffix == ".csv":
        dataframe = pd.read_csv(BytesIO(payload))
        sheets = [
            build_load_result_from_dataframe(
                dataframe=dataframe,
                source_name=file_name,
                file_type="csv",
                file_size_bytes=len(payload),
                sheet_name=Path(file_name).stem,
            )
        ]
    else:
        sheets = _load_excel_sheets_from_bytes(
            payload=payload,
            source_name=file_name,
            file_size_bytes=len(payload),
        )

    return WorkbookLoadResult(
        source_name=file_name,
        file_type=suffix.lstrip("."),
        file_size_bytes=len(payload),
        sheets=sheets,
    )


def load_evaluation_file(input_path: Path) -> LoadResult:
    workbook = load_workbook_file(input_path)
    if not workbook.sheets:
        raise ValueError("No readable sheet found in input file.")
    return workbook.sheets[0]


def load_uploaded_bytes(file_name: str, payload: bytes) -> LoadResult:
    workbook = load_uploaded_workbook(file_name, payload)
    if not workbook.sheets:
        raise ValueError("No readable sheet found in uploaded file.")
    return workbook.sheets[0]


def load_pasted_workbook(raw_text: str, source_name: str = "pasted_table") -> WorkbookLoadResult:
    load_result = load_pasted_table(raw_text, source_name)
    return WorkbookLoadResult(
        source_name=source_name,
        file_type="pasted_text",
        file_size_bytes=load_result.file_info.file_size_bytes,
        sheets=[load_result],
    )


def load_pasted_table(raw_text: str, source_name: str = "pasted_table") -> LoadResult:
    if not raw_text.strip():
        raise ValueError("Pasted content is empty.")

    sample = raw_text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
        separator = dialect.delimiter
    except csv.Error:
        separator = "\t" if "\t" in sample else ","

    dataframe = pd.read_csv(StringIO(raw_text), sep=separator)
    return build_load_result_from_dataframe(
        dataframe=dataframe,
        source_name=source_name,
        file_type="pasted_text",
        file_size_bytes=len(raw_text.encode("utf-8")),
        sheet_name="pasted_table",
    )


def build_load_result_from_dataframe(
    dataframe: pd.DataFrame,
    source_name: str,
    file_type: str,
    file_size_bytes: int,
    sheet_name: str | None = None,
) -> LoadResult:
    file_info = FileInfo(
        path=source_name,
        file_type=file_type,
        row_count=len(dataframe),
        column_count=len(dataframe.columns),
        file_size_bytes=file_size_bytes,
    )
    detected_columns = [str(column) for column in dataframe.columns.tolist()]
    return LoadResult(
        dataframe=dataframe,
        file_info=file_info,
        detected_columns=detected_columns,
        sheet_name=sheet_name,
    )


def _load_excel_sheets_from_bytes(payload: bytes, source_name: str, file_size_bytes: int) -> list[LoadResult]:
    excel_file = pd.ExcelFile(BytesIO(payload))
    sheet_results: list[LoadResult] = []
    for sheet_name in excel_file.sheet_names:
        dataframe = pd.read_excel(BytesIO(payload), sheet_name=sheet_name)
        if dataframe.empty and len(dataframe.columns) == 0:
            continue
        sheet_results.append(
            build_load_result_from_dataframe(
                dataframe=dataframe,
                source_name=source_name,
                file_type="xlsx",
                file_size_bytes=file_size_bytes,
                sheet_name=sheet_name,
            )
        )
    return sheet_results
