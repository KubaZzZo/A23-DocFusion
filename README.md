# DocFusion 文档理解与数据融合系统

DocFusion 是面向第十七届中国大学生服务外包创新创业大赛 A23 题目的桌面端项目，围绕“文档理解”和“数据融合”两条主线，提供多格式文档解析、OCR、实体提取、模板自动填写、跨文档融合分析、新闻采集与本地 API 服务等能力。

项目采用 **PyQt6 桌面端 + FastAPI 本地服务 + SQLite + LLM** 的组合架构，既可以作为比赛演示作品，也适合作为本地部署和二次开发的基础系统。

---

## 项目亮点

- 多格式文档统一处理：支持 `docx`、`xlsx`、`md`、`txt`、`pdf`、`png`、`jpg`、`jpeg`、`bmp`
- 图片 OCR 集成：支持 `pytesseract + Tesseract-OCR`
- LLM 驱动的实体提取：覆盖人名、机构、日期、金额、电话、邮箱、地址、编号、自定义实体
- 文档智能操作：支持格式调整、编辑、查找替换、提取和结构化处理
- 数据融合分析：支持跨文档实体关联、融合统计、融合报告导出
- 桌面端问答体验：可基于实体库进行智能问答
- 本地 RESTful API：便于联调、集成和扩展
- 比赛级交付：包含测试、脚本、配置说明和快速启动方式

---

## 核心功能

### 1. 文档理解

- 多格式文档解析
- 图片 OCR
- 单文档实体提取
- 批量文档实体提取
- 自然语言驱动的文档智能操作

### 2. 数据融合

- 跨文档实体关联
- 实体关键词搜索
- 融合统计与融合报告导出
- 实体智能问答

### 3. 业务能力

- 实体导出 CSV / Excel
- 模板自动填写（`xlsx` / `docx`）
- 新闻爬取、文章入库、文档生成、实体提取
- 本地 API 服务与接口文档

---

## 技术栈

- 桌面端：PyQt6
- API 服务：FastAPI、Uvicorn
- 数据库：SQLite、SQLAlchemy
- 文档处理：python-docx、openpyxl、PyMuPDF
- OCR：pytesseract、Pillow、Tesseract-OCR
- LLM：Ollama、本地模型、OpenAI 兼容接口
- 爬虫：httpx、BeautifulSoup4、lxml
- 测试：pytest

---

## 系统架构

```text
用户操作
   |
   v
PyQt6 Desktop UI
   |----------------------.
   |                      |
   v                      v
Core Workflows        FastAPI Local API
   |                      |
   v                      v
Document / Entity / Template / Crawler Services
   |
   v
SQLite + Local Files + LLM Providers
```

架构特点：

- 桌面界面与本地 API 共存，适合单机演示和本地工具化使用
- 核心业务模块按解析、提取、填写、融合、爬虫拆分
- LLM 层独立封装，支持本地模型与云端兼容接口切换
- 数据通过 SQLite 和本地文件目录持久化，部署成本低

---

## 项目结构

```text
A23-DocFusion/
├─ api/                       # FastAPI 路由、认证、服务启动
├─ core/                      # 文档解析、提取、模板填写、智能操作、工作流
├─ crawler/                   # 新闻爬虫与文档生成
├─ data/                      # 运行数据目录（数据库、缓存、日志、导出等）
├─ db/                        # SQLAlchemy 模型与 DAO
├─ llm/                       # LLM 适配层、缓存、预设、健康检查
├─ tests/                     # 自动化测试与测试数据
├─ ui/                        # PyQt6 桌面界面
├─ utils/                     # 工具函数
├─ config.py                  # 全局配置
├─ main.py                    # 项目入口
├─ install_dependencies.bat   # 一键安装依赖脚本
├─ start_docfusion.bat        # 一键启动脚本
└─ requirements.txt           # Python 依赖
```

---

## 环境要求

建议环境：

- Windows 10 / 11
- Python 3.12 或 3.13
- 能正常使用 `pip`

可选环境：

- Tesseract-OCR：启用图片 OCR 时需要
- Ollama：使用本地大模型时需要

---

## 快速开始

如果你希望最快跑起来，推荐直接使用仓库自带脚本。

### 第一步：安装依赖

双击运行：

```text
install_dependencies.bat
```

这个脚本会自动完成：

- 检测 Python
- 安装 `requirements.txt`
- 校验核心 Python 依赖
- 检测 `Tesseract-OCR`
- 如果机器里没有 `Tesseract-OCR`，自动尝试安装
- 只有在安装 `Tesseract-OCR` 时才会按需请求管理员权限

### 第二步：启动项目

双击运行：

```text
start_docfusion.bat
```

这个脚本会自动完成：

- 检测 Python
- 检测核心依赖是否已安装
- 检测 OCR 环境
- 启动桌面端项目

---

## 脚本说明

### install_dependencies.bat

作用：

- 自动探测 `py -3.13`、`py -3.12`、`py`、`python`
- 执行 `pip install -r requirements.txt`
- 校验关键依赖是否可导入
- 自动安装 `Tesseract-OCR`

说明：

- 默认不要求管理员权限
- 仅在自动安装 `Tesseract-OCR` 时，会弹出 UAC 请求管理员权限
- 如果目标机器没有 `winget`，脚本会给出手动安装提示

### start_docfusion.bat

作用：

- 检查 Python 是否可用
- 检查 `PyQt6`、`fastapi`、`sqlalchemy` 等核心依赖是否存在
- 启动 `main.py`

说明：

- 如果依赖未安装，会提示先运行 `install_dependencies.bat`
- 脚本会输出本地 API 地址和接口文档地址

---

## 手动安装方式

如果你不想使用批处理脚本，也可以手动安装。

### 安装 Python 依赖

```bash
pip install -r requirements.txt
```

或者：

```bash
py -3.13 -m pip install -r requirements.txt
```

### 启动项目

```bash
python main.py
```

或者：

```bash
py -3.13 main.py
```

---

## OCR 配置说明

图片 OCR 依赖 **Tesseract-OCR**。

推荐安装来源：

- [Tesseract at UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki)

默认配置位于 `config.py`：

```python
OCR_CONFIG = {
    "tesseract_cmd": r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    "lang": "chi_sim+eng",
}
```

如果 Tesseract 安装在其他路径，可以：

- 修改 `config.py`
- 或设置环境变量 `TESSERACT_CMD`

例如：

```bash
set TESSERACT_CMD=D:\Tesseract-OCR\tesseract.exe
```

---

## LLM 配置说明

项目支持两类模型接入方式：

### 本地模型（Ollama）

先安装并启动 Ollama，然后拉取模型，例如：

```bash
ollama pull qwen2.5:7b
```

默认配置：

```text
Base URL: http://localhost:11434
Model: qwen2.5:7b
```

### 云端模型（OpenAI 兼容接口）

可以在桌面端设置页中配置：

- 云端供应商
- API Key
- Base URL
- 模型名称

当前预设包括：

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

## 使用说明

### 文档导入与解析

1. 打开“信息提取”或“文档智能操作”模块
2. 选择本地文档文件
3. 系统自动解析文本内容
4. 如果是图片文件，将通过 OCR 提取文本

### 实体提取

1. 打开文档
2. 点击“提取实体”
3. 系统调用当前配置的 LLM 进行识别
4. 提取结果入库，并可用于导出、问答和融合分析

### 批量提取

1. 点击“批量提取”
2. 选择多个文件
3. 系统依次完成解析、提取和入库

### 模板填写

1. 导入模板文件（`xlsx` 或 `docx`）
2. 系统分析模板字段
3. 自动匹配实体值
4. 用户确认后导出结果文件

### 数据融合

仪表盘支持查看：

- 实体类型分布
- 文档类型分布
- 实体关键词搜索
- 跨文档实体关联
- 实体智能问答
- 融合报告导出

---

## 本地 API

默认监听地址：

```text
http://127.0.0.1:8000
```

接口文档：

```text
http://127.0.0.1:8000/docs
```

健康检查：

```bash
curl http://127.0.0.1:8000/api/health
```

统计信息：

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

---

## 测试

执行全部测试：

```bash
pytest tests
```

或：

```bash
py -3.13 -m pytest tests
```

说明：

- 当前脚本专项测试已通过
- 工作区里还存在 2 个既有 UI 线程测试问题，不是本次脚本改动引入

---

## 常见问题

### 1. 双击脚本没有反应

请先确认：

- 已安装 Python
- `python` 或 `py` 命令在系统 PATH 中可用

### 2. OCR 无法使用

请确认：

- `Tesseract-OCR` 已安装
- 路径是否与 `config.py` 中一致
- 必要时配置 `TESSERACT_CMD`

### 3. 云端模型连接失败

请确认：

- API Key 是否正确
- Base URL 是否正确
- 第三方中转站是否兼容 OpenAI 协议
- 设置页中的测试连接是否通过

### 4. 智能问答提示“根据当前实体库无法确定”

这通常表示：

- 文档还未完成实体提取
- 相关关键词未被抽取为实体
- 当前问题更偏全文检索，而不是实体问答

---

## 运行数据说明

以下内容属于运行时产物或本地文件，默认不建议提交到 Git：

- `data/docfusion.db`
- `data/settings.json`
- `data/uploads/`
- `data/outputs/`
- `data/crawled/`
- `data/backups/`
- `data/cache/`
- `data/logs/`

---

## 仓库地址

- GitHub: [https://github.com/KubaZzZo/A23-DocFusion](https://github.com/KubaZzZo/A23-DocFusion)

---

## 说明

本项目当前定位为：

- 比赛作品
- 本地部署工具
- 可继续扩展的桌面端文档处理系统

默认监听 `127.0.0.1`，更适合单机环境演示、开发和调试。
