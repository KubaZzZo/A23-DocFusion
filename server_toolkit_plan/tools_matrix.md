# 预装工具矩阵

## 优先级定义

| 优先级 | 含义 | 安装策略 |
| --- | --- | --- |
| P0 | 第一版最小可用镜像必装，覆盖 80% 常见任务 | 默认进入 `docfusion-worker` |
| P1 | 第二阶段增强工具，覆盖进阶提取、PDF 和匹配场景 | 按服务器资源和需求加入 |
| P2 | 特定场景工具，体积或资源占用较高 | 独立镜像或按需启用 |

## P0 最小可用镜像

第一版建议只安装以下工具，避免镜像过重：

- 系统工具：LibreOffice、Pandoc、Tesseract OCR、poppler-utils。
- Python 包：python-docx、docxtpl、openpyxl、pandas、PyMuPDF、pypdf、Pillow、opencv-python-headless、python-magic、Jinja2。
- 项目工具：`docfusion-cli`，命令前缀统一为 `docfusion`。

PaddleOCR、ClamAV、ImageMagick、reportlab、duckdb 不进入第一版最小镜像。

## 格式转换

| 工具 | 优先级 | 适合场景 | 不适合场景 | 安装方式 |
| --- | --- | --- | --- | --- |
| LibreOffice headless | P0 | Office 文档转 PDF、docx/xlsx/pptx 互转 | 精细内容抽取、复杂版式修复 | `apt install libreoffice` |
| Pandoc | P0 | Markdown、HTML、docx、txt、LaTeX 互转 | 扫描件、复杂 PDF 还原 | `apt install pandoc` |
| poppler-utils | P0 | PDF 转图片、页数检查、文本粗提取 | 复杂表格结构化抽取 | `apt install poppler-utils` |
| qpdf | P1 | PDF 合并、拆分、线性化、加解密 | Word/Excel 编辑 | `apt install qpdf` |

## Word 编辑与生成

| 工具 | 优先级 | 适合场景 | 不适合场景 | 安装方式 |
| --- | --- | --- | --- | --- |
| python-docx | P0 | 段落、字体、字号、表格、页边距、标题样式 | 高保真复杂版式、宏文档 | `pip install python-docx` |
| docxtpl | P0 | Word 模板填充、合同、报告、通知生成 | 任意自然语言排版决策 | `pip install docxtpl` |
| Jinja2 | P0 | 模板文本、HTML、Markdown 内容生成 | 二进制 Office 文档直接修改 | `pip install Jinja2` |

## Excel 与数据融合

| 工具 | 优先级 | 适合场景 | 不适合场景 | 安装方式 |
| --- | --- | --- | --- | --- |
| openpyxl | P0 | xlsx 读写、单元格、样式、公式、填表 | 超大数据量分析 | `pip install openpyxl` |
| pandas | P0 | 表格清洗、合并、统计、CSV/Excel 导出 | 保留复杂 Excel 样式 | `pip install pandas` |
| rapidfuzz | P1 | 字段名、机构名、客户名模糊匹配 | 语义理解、长文本摘要 | `pip install rapidfuzz` |
| duckdb | P2 | 多源表格 SQL 查询、临时分析 | 简单填表任务 | `pip install duckdb` |
| xlsxwriter | P2 | 大批量新建 Excel 报表 | 读取或修改现有 xlsx | `pip install xlsxwriter` |

## PDF 处理

| 工具 | 优先级 | 适合场景 | 不适合场景 | 安装方式 |
| --- | --- | --- | --- | --- |
| PyMuPDF | P0 | PDF 文本、图片、页面渲染、基础批注 | 表格结构精确还原 | `pip install PyMuPDF` |
| pypdf | P0 | PDF 合并、拆分、旋转、元数据 | OCR、图片文字识别 | `pip install pypdf` |
| pdfplumber | P1 | PDF 表格提取、坐标文本分析 | 扫描件无 OCR 文本 | `pip install pdfplumber` |
| reportlab | P2 | 从结构化数据生成 PDF、证书、报表 | 修改已有复杂 PDF | `pip install reportlab` |

## OCR 与图片处理

| 工具 | 优先级 | 适合场景 | 不适合场景 | 安装方式 |
| --- | --- | --- | --- | --- |
| Tesseract OCR | P0 | 图片、扫描件、普通中英文 OCR | 票据、复杂版面、手写体 | `apt install tesseract-ocr tesseract-ocr-chi-sim tesseract-ocr-eng` |
| Pillow | P0 | 图片格式转换、缩放、基础处理 | 图像识别算法 | `pip install Pillow` |
| opencv-python-headless | P0 | 倾斜校正、二值化、裁切、去噪 | OCR 模型本身 | `pip install opencv-python-headless` |
| PaddleOCR | P2 | 中文票据、截图、复杂版面识别 | 轻量镜像、低内存环境 | `pip install paddleocr paddlepaddle` |
| ImageMagick | P2 | 批量图片转换、复杂图片流水线 | 简单图片缩放 | `apt install imagemagick` |

## 文件安全

| 工具 | 优先级 | 适合场景 | 不适合场景 | 安装方式 |
| --- | --- | --- | --- | --- |
| python-magic | P0 | magic bytes 文件类型嗅探 | 病毒查杀 | `pip install python-magic` |
| oletools | P1 | Office 宏和可疑内容检查 | 非 Office 文件扫描 | `pip install oletools` |
| ClamAV | P2 | 病毒扫描、企业部署增强 | 轻量 MVP 镜像 | `apt install clamav` |

## docfusion-cli 命令映射

```text
docfusion convert        -> LibreOffice / Pandoc / pandas
docfusion format-docx    -> python-docx
docfusion fill-template  -> docxtpl / openpyxl
docfusion merge          -> pypdf / python-docx
docfusion split          -> pypdf
docfusion extract        -> PyMuPDF / pdfplumber / EntityExtractor
docfusion ocr            -> Tesseract / PaddleOCR + OpenCV
docfusion generate       -> docxtpl / Jinja2 / reportlab
docfusion validate       -> python-magic / oletools
```

## 镜像体积控制

| 层 | 估算大小 |
| --- | --- |
| `python:3.11-slim` | 约 150 MB |
| LibreOffice + Pandoc | 约 500 MB |
| Tesseract + 中文语言包 | 约 80 MB |
| P0 Python 依赖 | 约 300 MB |
| poppler-utils | 约 50 MB |
| 合计 | 约 1 GB |

PaddleOCR 可能额外增加 1.5 GB 以上，建议作为独立 OCR 增强镜像。
