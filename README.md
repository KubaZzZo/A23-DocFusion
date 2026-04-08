# DocFusion 文档理解与多源数据融合系统

DocFusion 是面向第十七届中国大学生服务外包创新创业大赛 A23 题目的桌面端系统，围绕“文档理解”和“数据融合”两个核心目标，提供多格式文档解析、LLM 实体提取、模板表格自动填写、跨文档实体关联、实体智能问答、新闻数据采集和 RESTful API 集成能力。

## 功能特性

- 多格式文档解析：支持 `docx`、`xlsx`、`md`、`txt`、`pdf`、`png`、`jpg`、`jpeg`、`bmp`。
- 图片 OCR：通过 `pytesseract` 和 Tesseract-OCR 从图片中识别文字。
- 自然语言文档操作：支持通过指令进行格式调整、编辑、查找替换、内容提取和结构操作，并自动备份原文件。
- 实体信息提取：基于 LLM 提取人名、机构、日期、金额、电话、邮箱、地址、编号、自定义实体等信息。
- 批量文档提取：支持一次选择多个本地文档，依次解析、抽取实体并入库。
- 实体导出：支持将实体数据导出为 CSV（UTF-8 BOM）和 Excel。
- 模板自动填写：支持 `xlsx`、`docx` 模板字段识别、语义匹配、用户确认和结果文件导出。
- 数据融合分析：支持跨文档实体关联视图，展示同一实体在多个文档中的出现情况。
- 融合报告导出：支持导出跨文档实体关联和融合统计 Excel 报告。
- 实体智能问答：基于已提取实体库回答问题，例如“张三的电话是多少？”。
- 新闻数据采集：支持百度百家号、澎湃新闻、新浪新闻、36 氪等来源的文章爬取、文档生成和入库提取。
- RESTful API：内置 FastAPI 服务，提供文档管理、实体查询/导出、模板填写、文章查询和系统统计接口。

## 技术栈

- 桌面端：PyQt6
- API 服务：FastAPI、Uvicorn
- 数据库：SQLite、SQLAlchemy
- 文档解析：python-docx、openpyxl、PyMuPDF
- OCR：pytesseract、Pillow、Tesseract-OCR
- LLM：Ollama 本地模型、OpenAI 兼容 API
- 爬虫：httpx、BeautifulSoup4、lxml
- 测试：pytest

## 项目结构

```text
A23-DocFusion/
├── api/                 # FastAPI 服务与路由
├── core/                # 文档解析、实体提取、模板填写、文档指令操作
├── crawler/             # 新闻爬虫与测试文档生成
├── data/                # 运行数据目录（数据库、上传、输出、日志等，已被 .gitignore 忽略）
├── db/                  # SQLAlchemy 模型与 DAO
├── llm/                 # LLM 抽象接口、本地/云端客户端、缓存
├── tests/               # 自动化测试与测试数据
├── ui/                  # PyQt6 桌面界面
├── utils/               # 文件工具
├── config.py            # 全局配置
├── main.py              # 桌面端入口
└── requirements.txt     # Python 依赖
```

## 安装依赖

建议使用 Python 3.12 或 3.13。

```bash
pip install -r requirements.txt
```

如果需要图片 OCR，还需要安装系统级 Tesseract-OCR。Windows 推荐安装包：

```text
https://github.com/UB-Mannheim/tesseract/wiki
```

默认配置路径为：

```text
C:\Program Files\Tesseract-OCR\tesseract.exe
```

如果安装在其他位置，可以设置环境变量：

```bash
set TESSERACT_CMD=D:\你的路径\Tesseract-OCR\tesseract.exe
```

或修改 `config.py` 中的 `OCR_CONFIG`。

## LLM 配置

默认使用 Ollama 本地模型：

```bash
ollama pull qwen2.5:7b
```

也可以在应用内“设置”界面切换到 OpenAI 兼容 API，并配置 API Key、Base URL 和模型名称。

常用环境变量：

```bash
set LLM_PROVIDER=ollama
set OLLAMA_BASE_URL=http://localhost:11434
set OLLAMA_MODEL=qwen2.5:7b

set OPENAI_API_KEY=你的APIKey
set OPENAI_BASE_URL=https://api.openai.com/v1
set OPENAI_MODEL=gpt-4o-mini
```

## 启动桌面应用

```bash
python main.py
```

应用启动后会自动初始化 SQLite 数据库，并在后台启动本地 API 服务：

```text
http://127.0.0.1:8000/docs
```

## 运行测试

```bash
pytest tests
```

当前已验证测试结果：

```text
51 passed
```

## API 示例

健康检查：

```bash
curl http://127.0.0.1:8000/api/health
```

获取统计数据：

```bash
curl http://127.0.0.1:8000/api/statistics
```

导出实体 CSV：

```bash
curl -o entities.csv "http://127.0.0.1:8000/api/entities/export?fmt=csv"
```

导出实体 Excel：

```bash
curl -o entities.xlsx "http://127.0.0.1:8000/api/entities/export?fmt=xlsx"
```

## 运行数据说明

以下运行产物不会提交到 Git：

- `data/docfusion.db`
- `data/uploads/`
- `data/outputs/`
- `data/crawled/`
- `data/backups/`
- `data/cache/`
- `data/logs/`
- `__pycache__/`
- `.pytest_cache/`

## GitHub 仓库

当前仓库地址：

```text
https://github.com/KubaZzZo/A23-DocFusion
```

仓库当前为私有仓库（PRIVATE）。
