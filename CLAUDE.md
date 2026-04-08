# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

DocFusion（A23赛题）是一个文档理解与多源数据融合桌面系统，前端 PyQt6 + 后端 FastAPI（同进程线程启动），SQLite 持久化，LLM 驱动实体提取和模板填写。

## 常用命令

```bash
# 安装依赖
pip install -r requirements.txt

# 启动桌面应用（同时启动 API 服务 http://127.0.0.1:8000）
python main.py

# 单独启动 API 服务
python -m api.server

# 运行全部测试
pytest tests/

# 运行单个测试文件
pytest tests/test_parser.py -v

# 运行单个测试方法
pytest tests/test_database.py::TestDocumentDAO::test_create_and_get -v
```

## 架构

```
main.py                  # 入口：初始化日志 → apply_saved_settings → init_db → run_app
├── ui/main_window.py    # QMainWindow，包含 5 个 Tab 面板 + 菜单 + LLM 切换
│   ├── dashboard_panel  # 数据概览（统计 DAO 数据）
│   ├── doc_panel        # 文档智能操作（自然语言指令 → DocCommander）
│   ├── extract_panel    # 信息提取（文档解析 → 实体提取）
│   ├── fill_panel       # 表格自动填写（模板分析 → 实体匹配 → 填充）
│   └── crawler_panel    # 新闻爬虫（爬取 → 生成文档）
├── api/server.py        # FastAPI，daemon 线程启动，提供 RESTful 接口
└── config.py            # 全局配置（路径、LLM、分块参数、爬虫参数）
```

### 核心调用链

1. **文档解析**: `DocumentParser.parse(path)` → 返回 `{"text", "file_type", "metadata"}`
2. **实体提取**: `TextChunker.chunk(text)` → 分块 → `EntityExtractor.extract(text)` → LLM 并发提取 → 合并去重
3. **模板填写**: `TemplateFiller.analyze_template()` → 识别字段 → `SemanticMatcher` 匹配实体 → 填充 xlsx
4. **文档操作**: `DocCommander.parse_command()` → LLM 解析指令 → `execute()` 执行（自动备份到 `data/backups/`）

### LLM 层

`llm/` 包提供工厂模式：`get_llm(provider)` 返回 `OllamaClient` 或 `CloudClient`，均继承 `BaseLLM`。`llm/cache.py` 提供 LLM 结果缓存。所有 LLM 调用都是 async。

### 数据层

- ORM: SQLAlchemy，模型在 `db/models.py`（Document, Entity, Template, FillTask, CrawledArticle）
- DAO: `db/database.py` 中的静态类（DocumentDAO, EntityDAO, TemplateDAO, FillTaskDAO, CrawledArticleDAO）
- 所有 DAO 方法在返回前 `expunge` ORM 对象，确保脱离 session 后属性可访问
- 使用 `session_scope()` 上下文管理器管理事务

### 数据目录

所有运行时数据在 `data/` 下：`uploads/`（上传文件）、`outputs/`（输出文件）、`crawled/`（爬取内容）、`backups/`（操作备份）、`docfusion.db`、`settings.json`

## 关键约定

- UI 面板中的异步 LLM 调用通过 `QThread` + `asyncio.new_event_loop()` 执行，信号槽通信回主线程
- 文件上传使用 `utils/file_utils.safe_copy()` 避免同名覆盖（自动加时间戳）
- API Key 在 `settings.json` 中 base64 编码存储，`settings_dialog.py` 中 `_encode_key/_decode_key` 处理
- LLM provider 切换通过 `config.LLM_CONFIG["provider"]` 全局字典，运行时可切换
- 项目语言为中文，UI 文本、注释、文档均使用中文
