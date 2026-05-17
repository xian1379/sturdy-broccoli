from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.deepseek_eval_agent.detector import detect_analysis_mode, detect_table_theme
from src.deepseek_eval_agent.loader import load_pasted_table, load_workbook_file
from src.deepseek_eval_agent.pipeline import run_pipeline_from_path


class PipelineSmokeTest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["LLM_API_KEY"] = ""

    def test_pasted_table_loader(self) -> None:
        raw_text = (
            "experiment_id\tmodel_name\tdataset\tprompt_version\taccuracy\tf1\tavg_latency_ms\tnotes\n"
            "exp-001\tdeepseek-chat\tmath_eval\tv1\t0.89\t0.89\t1250\tbaseline"
        )
        load_result = load_pasted_table(raw_text)
        self.assertEqual(load_result.file_info.file_type, "pasted_text")
        self.assertEqual(load_result.file_info.row_count, 1)
        self.assertIn("accuracy", load_result.detected_columns)

    def test_detect_eval_theme(self) -> None:
        theme_info = detect_table_theme(
            ["experiment_id", "model_name", "dataset", "accuracy", "f1", "avg_latency_ms"]
        )
        self.assertEqual(theme_info["table_theme"], "eval")

    def test_detect_business_theme_for_multi_sheet_workbook(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workbook_path = Path(tmpdir) / "business.xlsx"
            with pd.ExcelWriter(workbook_path) as writer:
                pd.DataFrame(
                    {
                        "地市": ["贵阳", "遵义"],
                        "项目名称": ["项目A", "项目B"],
                        "合同金额": [100, 200],
                    }
                ).to_excel(writer, sheet_name="24-25", index=False)
                pd.DataFrame(
                    {
                        "省分": ["贵州", "贵州"],
                        "客户名称": ["客户A", "客户B"],
                        "6税率金额": [10, 20],
                    }
                ).to_excel(writer, sheet_name="2023", index=False)

            workbook = load_workbook_file(workbook_path)
            mode_info = detect_analysis_mode(workbook)
            self.assertEqual(mode_info["mode"], "universal")
            self.assertEqual(mode_info["table_theme"], "business")
            self.assertEqual(mode_info["sheet_count"], 2)

    def test_universal_pipeline_for_eval_sample(self) -> None:
        root = Path(__file__).resolve().parents[1]
        sample_path = root / "sample_data" / "eval_results.csv"
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "eval_report.md"
            pipeline_result = run_pipeline_from_path(root, sample_path, output_path)
            self.assertEqual(pipeline_result.analysis_mode, "universal")
            self.assertEqual(pipeline_result.table_theme, "eval")
            self.assertEqual(len(pipeline_result.sheet_results), 1)
            self.assertEqual(pipeline_result.sheet_results[0].table_theme, "eval")
            self.assertTrue(output_path.exists())

    def test_universal_pipeline_for_multi_sheet_workbook(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmpdir:
            workbook_path = Path(tmpdir) / "business.xlsx"
            output_path = Path(tmpdir) / "report.md"
            with pd.ExcelWriter(workbook_path) as writer:
                pd.DataFrame(
                    {
                        "地市": ["贵阳", "遵义", "贵阳"],
                        "项目名称": ["项目A", "项目B", "项目C"],
                        "6税率未计收金额": [100, 50, 300],
                        "合同编号": ["A-1", "B-1", "C-1"],
                    }
                ).to_excel(writer, sheet_name="24-25", index=False)
                pd.DataFrame(
                    {
                        "省分": ["贵州", "贵州"],
                        "客户名称": ["客户A", "客户B"],
                        "合同金额（含税）万元": [74.0, 328.0],
                    }
                ).to_excel(writer, sheet_name="2023", index=False)

            pipeline_result = run_pipeline_from_path(root, workbook_path, output_path)
            self.assertEqual(pipeline_result.analysis_mode, "universal")
            self.assertEqual(pipeline_result.table_theme, "business")
            self.assertEqual(len(pipeline_result.sheet_results), 2)
            self.assertIn("24-25", pipeline_result.specialized_insights)
            self.assertTrue(output_path.exists())


if __name__ == "__main__":
    unittest.main()
