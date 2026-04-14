# DocFusion 文档理解与数据融合系统

DocFusion 是面向第十七届中国大学生服务外包创新创业大赛 A23 题目的桌面端项目，围绕“文档理解”和“数据融合”两条主线，提供文档解析、实体提取、模板填写、跨文档融合分析、新闻数据采集与本地 API 服务等能力。

本项目以 **PyQt6 桌面端 + FastAPI 本地服务 + SQLite + LLM** 为核心架构，适合用于比赛演示、二次开发和本地部署。

---

## 1. 功能概览

### 文档理解
- 支持多格式文档解析：`docx`、`xlsx`、`md`、`txt`、`pdf`、`png`、`jpg`、`jpeg`、`bmp`
- 支持图片 OCR（基于 `pytesseract + Tesseract-OCR`）
- 支持自然语言文档智能操作（格式调整、编辑、查找替换、内容提取、结构化处理）
- 支持单文档与批量文档实体提取

### 数据融合
- 支持跨文档实体关联分析
- 支持融合统计与融合报告导出
- 支持实体关键词搜索
- 支持实体智能问答

### 业务功能
- 支持实体导出为 CSV / Excel
- 支持模板自动填写（`xlsx` / `docx`）
- 支持新闻爬取、文章入库、文档生成与实体提取
- 内置 RESTful API，便于和其他系统集成

---

## 2. 技术栈

- 桌面端：PyQt6
- API 服务：FastAPI、Uvicorn
- 数据库：SQLite、SQLAlchemy
- 文档处理：python-docx、openpyxl、PyMuPDF
- OCR：pytesseract、Pillow、Tesseract-OCR
- LLM：Ollama、本地模型、OpenAI 兼容云端接口
- 爬虫：httpx、BeautifulSoup4、lxml
- 测试：pytest

---

## 3. 项目结构

```text
A23-DocFusion/
├─ api/              # FastAPI 路由与接口
├─ core/             # 文档解析、实体提取、模板填写、文档智能操作
├─ crawler/          # 新闻爬虫与测试文档生成
├─ data/             # 运行时数据目录（数据库、上传、输出、缓存、日志等）
├─ db/               # SQLAlchemy 模型与 DAO
├─ llm/              # LLM 适配层、本地/云端客户端、缓存
├─ tests/            # 自动化测试与测试数据
├─ ui/               # PyQt6 桌面界面
├─ utils/            # 工具函数
├─ config.py         # 全局配置
├─ main.py           # 项目入口
└─ requirements.txt  # Python 依赖
```

---

## 4. 环境要求

建议环境：
- Windows 10 / 11
- Python 3.12 或 3.13
- 已安装 Git（如需版本管理）

可选环境：
- Tesseract-OCR（如果需要图片 OCR）
- Ollama（如果使用本地大模型）

---

## 5. 安装依赖

在项目根目录执行：

```bash
pip install -r requirements.txt
```

如果你使用的是 Python 3.13，可执行：

```bash
py -3.13 -m pip install -r requirements.txt
```

---

## 6. OCR 配置说明

如果需要识别图片中的文字，需要额外安装 **Tesseract-OCR**。

Windows 推荐安装包：
- [Tesseract at UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki)

默认路径配置在 `config.py`：

```python
OCR_CONFIG = {
    "tesseract_cmd": r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    "lang": "chi_sim+eng",
}
```

如果安装位置不同，可以：
- 修改 `config.py`
- 或设置环境变量 `TESSERACT_CMD`

例如：

```bash
set TESSERACT_CMD=D:\Tesseract-OCR\tesseract.exe
```

---

## 7. LLM 配置说明

项目支持两类模型接入方式：

### 7.1 本地模型（Ollama）

先安装并启动 Ollama，然后拉取模型，例如：

```bash
ollama pull qwen2.5:7b
```

默认配置：

```text
Base URL: http://localhost:11434
Model: qwen2.5:7b
```

### 7.2 云端模型（OpenAI 兼容接口）

你可以在桌面端“设置”中配置以下信息：
- 云端供应商
- API Key
- Base URL
- 模型名称

当前设置页已支持以下预设：
- OpenAI
- DeepSeek
- Moonshot
- 通义千问
- 智谱
- Claude（兼容接口）
- 自定义兼容接口

也支持通过环境变量配置：

```bash
set LLM_PROVIDER=openai
set OPENAI_API_KEY=your-api-key
set OPENAI_BASE_URL=https://api.openai.com/v1
set OPENAI_MODEL=gpt-4o-mini
```

---

## 8. 启动方式

### 8.1 启动桌面端

```bash
python main.py
```

或：

```bash
py -3.13 main.py
```

启动后会自动完成：
- 初始化日志
- 初始化数据库
- 启动 PyQt6 桌面程序
- 在后台启动本地 FastAPI 服务

### 8.2 本地 API 地址

默认监听：

```text
http://127.0.0.1:8000
```

接口文档：

```text
http://127.0.0.1:8000/docs
```

健康检查：

```text
http://127.0.0.1:8000/api/health
```

---

## 9. 开发使用说明

### 9.1 文档导入与解析
1. 打开“信息提取”或“文档智能操作”模块
2. 选择本地文档文件
3. 系统自动解析文本内容
4. 若为图片文件，将通过 OCR 提取文本

### 9.2 实体提取
1. 在“信息提取”模块中打开文档
2. 点击“提取实体”
3. 系统会调用当前配置的 LLM 进行识别
4. 结果会保存到数据库，并可直接导出

### 9.3 批量提取
1. 点击“批量提取”
2. 选择多个文件
3. 系统依次完成解析、提取和入库
4. 进度条会显示处理进度

### 9.4 模板填写
1. 导入模板文件（`xlsx` 或 `docx`）
2. 系统分析模板字段
3. 自动匹配实体值
4. 用户确认后导出结果文件

### 9.5 数据融合
在仪表盘中可以查看：
- 实体类型分布
- 文档类型分布
- 实体关键词搜索
- 跨文档实体关联
- 实体智能问答
- 融合报告导出

---

## 10. API 示例

### 健康检查

```bash
curl http://127.0.0.1:8000/api/health
```

### 查看统计信息

```bash
curl http://127.0.0.1:8000/api/statistics
```

### 导出实体 CSV

```bash
curl -o entities.csv "http://127.0.0.1:8000/api/entities/export?fmt=csv"
```

### 导出实体 Excel

```bash
curl -o entities.xlsx "http://127.0.0.1:8000/api/entities/export?fmt=xlsx"
```

---

## 11. 运行测试

执行全部测试：

```bash
pytest tests
```

如果使用 Python 3.13：

```bash
py -3.13 -m pytest tests
```

当前已验证测试结果：

```text
64 passed
```

---

## 12. 常见问题

### 12.1 图片 OCR 不生效
请检查：
- 是否已安装 Tesseract-OCR
- `TESSERACT_CMD` 或 `config.py` 中路径是否正确

### 12.2 云端模型连接失败
请检查：
- API Key 是否填写正确
- Base URL 是否正确
- 所使用的第三方中转站是否兼容 OpenAI 协议
- 设置页“测试连接”是否能通过

### 12.3 智能问答提示“根据当前实体库无法确定”
这通常表示：
- 当前问题对应的信息没有被提取为实体
- 相关文档尚未完成实体提取
- 问题更偏全文检索，而非实体问答

### 12.4 文档智能操作仅推荐用于 `.docx`
虽然系统支持多格式解析，但文档智能操作的格式级修改主要面向 `docx` 文档。

---

## 13. 运行数据说明

以下内容属于运行时数据或本地产物，默认不会提交到 Git：
- `data/docfusion.db`
- `data/settings.json`
- `data/uploads/`
- `data/outputs/`
- `data/crawled/`
- `data/backups/`
- `data/cache/`
- `data/logs/`
- `__pycache__/`
- `.pytest_cache/`

---

## 14. 仓库地址

GitHub 仓库：
- [https://github.com/KubaZzZo/A23-DocFusion](https://github.com/KubaZzZo/A23-DocFusion)

---

## 15. 说明

本项目当前定位为比赛作品与本地部署项目，默认监听 `127.0.0.1`，适合单机环境演示、开发和调试。
