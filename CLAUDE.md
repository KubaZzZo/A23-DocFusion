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
├── ui/main_window.py    # QMainWindow，包含 5 个 Tab 面板 + 菜单 + LLM 状态栏
│   ├── dashboard_panel  # 数据概览（统计 DAO 数据，后台 QThread 刷新）
│   ├── doc_panel        # 文档智能操作（自然语言指令 → DocCommander）
│   ├── extract_panel    # 信息提取（文档解析 → 实体提取，支持单文档/批量）
│   ├── fill_panel       # 表格自动填写（模板分析 → 语义匹配 → 填充确认）
│   └── crawler_panel    # 新闻爬虫（并发抓取 → 生成文档 → 导入+实体提取）
├── api/server.py        # FastAPI，daemon 线程启动，提供 RESTful 接口
└── config.py            # 全局配置（路径、LLM、分块参数、上传限制、爬虫参数）
```

### 核心调用链

1. **文档解析**: `DocumentParser.parse(path)` → 适配器模式按扩展名分发 → 返回 `{"text", "file_type", "metadata"}`
2. **实体提取**: `TextChunker.chunk(text)` → 分块（含超长段强制拆分） → `EntityExtractor.extract(text)` → LLM 并发提取 → 合并去重
3. **模板填写**: `TemplateFiller.analyze_template()` → 识别字段 → `SemanticMatcher.match()` 语义匹配 → 用户确认 → 填充输出
4. **文档操作**: `DocCommander.parse_command()` → Pydantic 验证 → `execute()` — 自动备份到 `data/backups/`，失败自动恢复

### LLM 层

`llm/` 包提供工厂模式：`get_llm(provider)` 返回 `OllamaClient` 或 `CloudClient`，均继承 `BaseLLM`。所有 LLM 调用都是 async。

- `llm/cache.py` — SHA256 哈希 + OrderedDict LRU（max 300）内存缓存 + 文件缓存
- `llm/prompt_safety.py` — `wrap_untrusted_input()` 用 XML 标签包裹用户输入，防止 prompt 注入
- JSON 解析统一走 `llm/json_utils.py` 去除 markdown 围栏 + 规范化

### 数据层

- ORM: SQLAlchemy，模型在 `db/models.py`（Document, Entity, Template, FillTask, CrawledArticle）
- Entity 表在 `document_id`、`entity_type`、`entity_value` 上有索引；`ensure_entity_indexes()` 在 `init_db` 时自动创建
- DAO: `db/database.py` 中的静态类，全部 `get_all()` 支持 `limit`/`offset` 分页
- 所有 DAO 方法支持可选 `session` 参数，传入时走外部事务、不自动 commit/expunge
- 默认通过 `session_scope()` 管理事务，返回前 `expunge` ORM 对象避免 `DetachedInstanceError`
- `get_cross_document_entities()` 使用纯 SQL `GROUP BY` + `HAVING COUNT(DISTINCT ...)` 聚合

### API 安全层

- `api/auth.py`：`require_local_bearer_token` 依赖注入，验证 loopback 来源 + Bearer token + Origin/Referer（非安全方法）
- `/api/*` 路由统一挂载 `require_local_bearer_token`；`/api/health` 公开
- API token 存储在 `data/api_token.txt`，首次启动自动生成

### 安全模块

- `core/file_signature.py` — 上传文件 magic bytes 验证（PDF/DOCX/XLSX/图片）
- `core/upload_limits.py` — 上传大小限制（默认 50MB，`config.MAX_UPLOAD_SIZE`）
- `core/spreadsheet_safety.py` — `escape_formula_value()` 防止 CSV/XLSX 公式注入

## 关键约定

- UI 面板中的异步 LLM 调用通过 `QThread` (`TaskWorker`/`ProgressTaskWorker`) + `asyncio.new_event_loop()` 执行，信号槽通信回主线程
- 创建新 `TaskWorker` 前必须检查 `self.worker.isRunning()` 防止 use-after-free
- API Key 使用 Windows DPAPI (`CryptProtectData`) 加密存储，带 `dpapi:` 前缀；兼容旧版 base64 编码值
- `settings_store.apply_settings` 对运行时 key 使用 `api_key_ref` 引用而非直接存储明文
- LLM provider 切换通过 `config.LLM_CONFIG["provider"]` 全局字典，运行时可切换
- 文件上传使用 `FileTransaction` 上下文管理器确保失败回滚
- 项目语言为中文，UI 文本、注释、文档均使用中文
