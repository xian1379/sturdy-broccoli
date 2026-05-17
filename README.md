# Table Analysis Agent

这是一个面向结构化表格的分析项目。它接收 `csv`、`xlsx` 或从 Excel 复制的表格文本，自动识别表格主题，输出 Markdown 和 Word 报告。项目优先支持业务台账和财务类表格，也兼容评测表和未命中专项规则的通用表格。

## 启动方式

先安装依赖：

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

如果要启用 LLM 分析，总共两种方式：

- 复制 `.env.example` 为 `.env`，填写 `LLM_API_KEY`
- 启动前端后，在侧边栏直接输入 `API Key`

命令行启动：

```bash
python -m src.table_analysis_agent.main --input sample_data/eval_results.csv --output artifacts/report.md
```

前端启动：

```bash
streamlit run streamlit_app.py
```

命令行入口在 `src/table_analysis_agent/main.py`，前端入口在 `streamlit_app.py`。

## 示例输入 / 输出

项目自带示例输入：
`sample_data/eval_results.csv`

示例表头：

```csv
experiment_id,model_name,dataset,prompt_version,temperature,accuracy,precision,recall,f1,avg_latency_ms,cost_per_1k,error_rate,notes
```

运行后会生成：

- `artifacts/report.md`
- `artifacts/report.docx`

输出内容主要包括文件级总结、逐表结构分析、异常提示，以及在可用时由 LLM 生成的结论和建议。

## 模式说明

项目重点有两个专项：

- `business`：适合客户、项目、合同、回款、区域等业务台账类表格
- `financial`：适合金额、收入、成本、税率、余额、应收等财务类表格

如果列名特征没有明显命中这两个专项，就进入 `generic` 通用模式。也就是说，未命中专项并不代表无法分析，而是退回到一套更通用的结构化分析模板。

除此之外，如果表格中包含 `model_name`、`accuracy`、`f1`、`avg_latency_ms` 这类字段，还会命中评测增强逻辑。

## 关键代码

`src/table_analysis_agent/main.py` 是最直接的入口，职责很轻：解析 `--input`、`--output`、`--dump-json`，然后把输入交给主流水线。

`src/table_analysis_agent/analyzer.py` 前 136 行是 prompt 和 LLM 调用层的核心。这里做三件事：

- 组装 `system prompt` 和结构化 `user payload`
- 调用兼容 OpenAI 风格的 `/chat/completions`
- 在没有 API Key 或调用失败时，退回 `fallback_universal_analysis()`

`src/table_analysis_agent/generic.py` 第 24 到 75 行是通用表格分析的起点，也就是 `profile_table_structure()`。这一段负责先把每一列粗分成数值列、维度列、日期列、低价值列和 ID 列，再整理缺失率、重点列和 warning，供后续专项增强和通用分析复用。

## 测试

```bash
python -m unittest discover -s tests -q
```
