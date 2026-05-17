from __future__ import annotations

import argparse
import json
from pathlib import Path

from .pipeline import run_pipeline_from_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate an AI report from CSV/XLSX input.")
    parser.add_argument("--input", required=True, help="Path to input CSV/XLSX file.")
    parser.add_argument("--output", default="", help="Path to output Markdown report.")
    parser.add_argument("--dump-json", action="store_true", help="Print pipeline result JSON summary.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[2]
    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve() if args.output else (project_root / "artifacts" / "report.md")

    pipeline_result = run_pipeline_from_path(project_root, input_path, output_path)

    print(f"Report written to: {pipeline_result.report_path}")
    print(f"Analysis mode: {pipeline_result.analysis_mode}")
    if args.dump_json:
        print(json.dumps(pipeline_result.to_dict(), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
