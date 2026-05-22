# 场景映射

## 任务分级规则

自然语言指令先被后端解析成结构化执行计划，再交给工具层或 Codex CLI 执行。

| 级别 | 判断规则 | 执行方式 |
| --- | --- | --- |
| L1 | 单步、确定性、参数明确、无需阅读中间结果 | 后端直接生成一个 `docfusion` 命令 |
| L2 | 多步、顺序明确、每一步都能用固定工具完成 | 后端串联多个 `docfusion` 命令 |
| L3 | 需要判断、生成、改写、跨文档理解或根据中间结果调整下一步 | 后期交给 Codex CLI Agent |

默认策略：能归为 L1/L2 的任务不使用 Codex CLI。

## 标准执行计划 JSON

所有意图解析结果统一输出以下字段：

```json
{
  "level": "L2",
  "requires_agent": false,
  "inputs": ["input/report.docx"],
  "outputs": ["output/report.pdf"],
  "timeout_seconds": 180,
  "steps": [
    {
      "id": "step_1",
      "tool": "docfusion",
      "command": "format-docx",
      "args": {
        "input": "input/report.docx",
        "output": "work/report_formatted.docx",
        "heading_font": "SimHei",
        "heading_size": 18
      }
    },
    {
      "id": "step_2",
      "tool": "docfusion",
      "command": "convert",
      "args": {
        "input": "work/report_formatted.docx",
        "to": "pdf",
        "output": "output/report.pdf"
      }
    }
  ]
}
```

L3 任务允许增加 `agent_prompt`，但仍必须保留上述字段：

```json
{
  "level": "L3",
  "requires_agent": true,
  "inputs": ["input/a.docx", "input/b.pdf", "input/c.xlsx"],
  "outputs": ["output/project_report.docx", "output/project_report.pdf"],
  "timeout_seconds": 600,
  "steps": [],
  "agent_prompt": "只在 /workspace 内工作。根据 input/ 中的三份材料生成项目可行性报告，结果放到 output/。优先调用 docfusion-cli。"
}
```

## L1 场景

| 用户指令 | 执行计划 | 工具 |
| --- | --- | --- |
| 把这个 Word 转成 PDF | `docfusion convert input/a.docx --to pdf --output output/a.pdf` | LibreOffice |
| 把 Markdown 转成 Word | `docfusion convert input/a.md --to docx --output output/a.docx` | Pandoc |
| 合并这两个 PDF | `docfusion merge input/a.pdf input/b.pdf --output output/merged.pdf` | pypdf |
| 提取 PDF 的文本 | `docfusion extract input/a.pdf --type text --output output/a.txt` | PyMuPDF |
| Excel 转 CSV | `docfusion convert input/a.xlsx --to csv --output output/a.csv` | pandas |
| 识别这张图片里的文字 | `docfusion ocr input/scan.png --output output/scan.txt` | Tesseract |

## L2 场景

### 改格式后转换

```text
用户：把标题改成黑体 18 号，然后转成 PDF

step_1: docfusion format-docx input/report.docx --output work/report.docx --heading-font SimHei --heading-size 18
step_2: docfusion convert work/report.docx --to pdf --output output/report.pdf
```

### OCR 后提取字段

```text
用户：识别这张发票图片，提取金额、日期和销售方

step_1: docfusion ocr input/invoice.jpg --output work/invoice.txt
step_2: docfusion extract work/invoice.txt --schema amount,date,vendor --output output/entities.json
```

### 多文档合并并统一样式

```text
用户：把这三个 Word 合并成一个，并统一标题样式

step_1: docfusion merge input/a.docx input/b.docx input/c.docx --output work/merged.docx
step_2: docfusion format-docx work/merged.docx --output output/merged.docx --heading-font SimHei --heading-size 16
```

### 提取后填模板

```text
用户：从合同里提取甲乙方和金额，填到模板里

step_1: docfusion extract input/contract.pdf --schema party_a,party_b,amount --output work/entities.json
step_2: docfusion fill-template input/template.xlsx --data work/entities.json --output output/template_filled.xlsx
```

## L3 场景

L3 任务后期由 Codex CLI Agent 处理。Agent 仍然只能调用预装工具和 `docfusion-cli`，不能自由访问服务器文件。

| 用户指令 | 为什么是 L3 | Codex CLI 作用 |
| --- | --- | --- |
| 根据三份调研材料生成项目可行性报告 | 需要跨文档理解、生成大纲、生成正文 | 规划章节、调用提取和生成工具 |
| 把申报书改得更正式并补充缺失数据 | 需要判断语气、识别缺失字段、查找可补充材料 | 多步推理和改写 |
| 把这些文件按主题分类，每类生成摘要 | 需要内容聚类和多文档摘要 | 规划分类和摘要生成 |
| 根据中间结果决定下一步处理方式 | 固定后端计划无法提前确定完整步骤 | 读取中间结果后选择工具 |

## 关键词映射

| 关键词 | 默认意图 |
| --- | --- |
| 转成、转换、导出为 | `convert` |
| 字体、字号、加粗、行距、页边距、标题 | `format-docx` |
| 合并、拼接 | `merge` |
| 拆分、提取页面 | `split` |
| 提取、识别、抽取 | `extract` |
| 填写、填表、填充 | `fill-template` |
| 生成、创建、写一份 | `generate`，通常进入 L3 |
| OCR、识别文字、扫描件 | `ocr` |
| 统计、分析、汇总 | `analyze`，简单表格为 L1/L2，跨文档为 L3 |

## 分级兜底

- 如果用户只指定格式或样式，优先 L1/L2。
- 如果用户要求“帮我优化”“更正式”“补全”“根据材料写”，优先 L3。
- 如果文件类型不支持，任务创建阶段返回 `UNSUPPORTED_TYPE`。
- 如果 L3 Agent 失败，返回已生成的部分文件、失败步骤和错误日志，不自动无限重试。
