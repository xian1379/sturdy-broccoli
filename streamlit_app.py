from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import streamlit as st

from src.deepseek_eval_agent.detector import detect_analysis_mode
from src.deepseek_eval_agent.loader import load_pasted_workbook, load_uploaded_workbook
from src.deepseek_eval_agent.pipeline import run_pipeline_from_workbook


PROJECT_ROOT = Path(__file__).resolve().parent
ARTIFACT_DIR = PROJECT_ROOT / "artifacts"


st.set_page_config(page_title="DeepSeek Eval Agent", page_icon=":bar_chart:", layout="wide")


def main() -> None:
    st.title("DeepSeek Eval Agent")
    st.caption("上传或粘贴结构化表格，自动识别主题并生成 Markdown / Word 分析报告。")

    with st.sidebar:
        st.subheader("使用说明")
        st.markdown(
            "- 上传 `csv/xlsx`\n"
            "- 或直接粘贴从 Excel 复制出的表格文本\n"
            "- 自动识别评测、业务、财务或通用表格\n"
            "- 支持多 sheet 一次性分析\n"
            "- 可下载 Markdown 和 Word 报告"
        )
        st.info("如果表头不规范、包含大量说明文字，或存在复杂合并单元格，建议先整理后再分析。")

        st.subheader("API 配置")
        api_key_input = st.text_input(
            "DeepSeek API Key",
            type="password",
            value="",
            help="仅本次会话使用。留空时继续使用 .env 或系统环境变量中的 LLM_API_KEY。",
        )
        if api_key_input.strip():
            st.caption("当前会话将优先使用页面中输入的 API Key，不会写入本地文件。")
        elif os.getenv("LLM_API_KEY"):
            st.caption("当前未在页面中输入 API Key，将使用已有环境变量中的 LLM_API_KEY。")
        else:
            st.caption("当前未检测到 API Key；系统会自动退化为仅统计分析报告。")

    left, right = st.columns(2)
    with left:
        uploaded_file = st.file_uploader("上传文件", type=["csv", "xlsx"])
    with right:
        pasted_text = st.text_area(
            "或直接粘贴表格内容",
            height=240,
            placeholder="把从 Excel 复制的整块表格粘贴到这里，支持制表符或逗号分隔。",
        )

    if st.button("生成 AI 报告", type="primary", use_container_width=True):
        try:
            if api_key_input.strip():
                os.environ["LLM_API_KEY"] = api_key_input.strip()

            if uploaded_file is not None:
                workbook = load_uploaded_workbook(uploaded_file.name, uploaded_file.getvalue())
                input_path = Path(uploaded_file.name)
            elif pasted_text.strip():
                workbook = load_pasted_workbook(pasted_text)
                input_path = Path("pasted_table.csv")
            else:
                st.error("请先上传一个 csv/xlsx 文件，或者粘贴一份表格内容。")
                return

            mode_info = detect_analysis_mode(workbook)
            output_name = f"web_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            pipeline_result = run_pipeline_from_workbook(
                project_root=PROJECT_ROOT,
                input_path=input_path,
                workbook=workbook,
                output_path=ARTIFACT_DIR / output_name,
            )
        except Exception as exc:  # noqa: BLE001
            st.error(f"生成失败：{exc}")
            return

        st.success("总结文档已生成。")
        st.info(
            f"分析模式：`{pipeline_result.analysis_mode}` | "
            f"主体主题：`{pipeline_result.table_theme}` | "
            f"识别依据：{pipeline_result.mode_reason}"
        )

        st.subheader("检测到的工作表")
        for item in mode_info.get("sheet_detections", []):
            with st.expander(f"{item['sheet_name']} | theme={item['table_theme']}"):
                st.write(item)

        if workbook.sheets:
            st.subheader("字段与样例预览")
            for sheet in workbook.sheets:
                with st.expander(
                    f"{sheet.sheet_name or 'Sheet'} | rows={sheet.file_info.row_count} | cols={sheet.file_info.column_count}"
                ):
                    st.write({"detected_columns": sheet.detected_columns})
                    st.dataframe(sheet.dataframe.head(10), use_container_width=True)

        summary_col, report_col = st.columns([1, 1.25])
        with summary_col:
            st.subheader("文件级总结")
            st.write(pipeline_result.workbook_summary)

            st.subheader("逐表结构化分析")
            for sheet_result in pipeline_result.sheet_results:
                with st.expander(f"{sheet_result.sheet_name} | {sheet_result.table_theme}"):
                    st.write({"column_roles": sheet_result.column_roles})
                    st.write({"quality_summary": sheet_result.quality_summary})
                    st.write({"specialized_insights": sheet_result.specialized_insights})
                    st.write({"aggregation": sheet_result.aggregation})
        with report_col:
            _render_report_panel(pipeline_result.report_path)
    else:
        st.subheader("当前支持")
        st.markdown(
            "- 模型评测表：自动命中评测增强\n"
            "- 业务台账：自动命中业务增强\n"
            "- 金额 / 回款类表格：自动命中财务增强\n"
            "- 其他结构化表格：使用通用分析模板"
        )


def _render_report_panel(report_path: Path) -> None:
    st.subheader("总结文档正文")
    report_text = report_path.read_text(encoding="utf-8")
    st.markdown(report_text)
    docx_path = report_path.with_suffix(".docx")
    if docx_path.exists():
        st.download_button(
            "下载 Word 文档",
            data=docx_path.read_bytes(),
            file_name=docx_path.name,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )
    st.download_button(
        "下载 Markdown 文本",
        data=report_text,
        file_name=report_path.name,
        mime="text/markdown",
        use_container_width=True,
    )


if __name__ == "__main__":
    main()
