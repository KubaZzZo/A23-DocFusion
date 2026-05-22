# 服务器文档工具包规划

## 目标

把 DocFusion 的文档处理能力从桌面端扩展到服务器端，形成一个安全、可控、可维护的文档智能处理平台。用户在本地客户端提交自然语言指令和文件，服务器负责创建任务、解析意图、调用工具、隔离执行、返回结果文件和执行日志。

本目录只保存规划文档，不包含可执行代码。后续真正实现建议放入独立的 `cli/`、`server/` 或 worker 目录。

## 核心原则

1. **确定性优先**：转换格式、调整字体、填模板、合并拆分等明确任务，优先由 `docfusion-cli` 直接执行。
2. **工具层是产品核心**：`docfusion-cli` 封装文档处理、数据融合、模板生成和安全检查能力，是后端和 Codex CLI 共同调用的稳定接口。
3. **Agent 只做升级能力**：Codex CLI 后期只处理 L3 复杂任务，不替代基础工具层。
4. **容器隔离执行**：服务器上的每个任务运行在独立 Docker worker 中，只能访问本次任务目录。
5. **结果可追踪**：每个任务都必须有状态、结构化步骤日志、标准输出、错误日志和可回收的结果文件。

## 总体架构

```text
本地客户端
  -> 上传文件 + 自然语言指令
服务器 FastAPI
  -> 创建任务目录
  -> 校验文件
  -> 解析意图并生成执行计划
任务调度器
  -> L1/L2: Docker worker 调用 docfusion-cli
  -> L3: Docker worker 启动 Codex CLI Agent，再调用 docfusion-cli
任务目录
  -> input/ work/ output/ logs/ task.json
服务器 FastAPI
  -> 推送进度
  -> 返回日志
  -> 下载结果
本地客户端
  -> 展示流程和结果文件
```

## 实施路线

| 阶段 | 目标 | 产出 |
| --- | --- | --- |
| 阶段 1 | 实现 `docfusion-cli` 工具层，覆盖 L1/L2 确定性任务 | 可独立运行的 `docfusion` 命令 |
| 阶段 2 | 实现服务器任务 API、任务目录、日志、状态流转 | `/api/server-tasks` 任务闭环 |
| 阶段 3 | 实现 Docker worker 隔离执行 | 受限容器、超时控制、结果回收 |
| 阶段 4 | 本地客户端接入任务面板 | 提交任务、查看进度、下载结果 UI |
| 阶段 5 | 接入 Codex CLI，只处理 L3 复杂任务 | 可选高级 Agent 执行能力 |

第一版服务器能力优先覆盖 L1/L2 文档处理任务。Codex CLI 必须等 `docfusion-cli` 稳定后再接入。

## 任务分级

| 级别 | 定义 | 执行方式 | 示例 |
| --- | --- | --- | --- |
| L1 | 单步、确定性、参数清楚 | 直接调用 `docfusion-cli` | Word 转 PDF、PDF 合并、Excel 转 CSV |
| L2 | 多步、顺序明确、无需中间判断 | 后端生成执行计划，串联多个 `docfusion` 命令 | 改标题字体后转 PDF、OCR 后提取字段 |
| L3 | 需要判断、生成、改写、跨文档理解 | Codex CLI Agent 规划并调用 `docfusion-cli` | 根据多份材料生成报告、补全申报书 |

## 标准任务目录

所有服务器任务统一使用 Linux 路径：

```text
/var/docfusion/tasks/{task_id}/
  input/          # 用户上传文件，只读挂载给容器
  work/           # 中间文件
  output/         # 最终结果文件
  logs/           # stdout.log、stderr.log、steps.jsonl
  task.json       # 任务描述和执行计划
```

后端只从 `output/` 回收并返回结果文件。`work/` 和 `logs/` 用于调试、审计和进度展示。

## 与现有系统关系

- 复用 `docfusion_desktop/backend` 中已有能力：文档解析、实体抽取、模板填充、语义匹配、LLM 调用。
- 不修改现有桌面端 UI、当前 API、数据库模型和本地工作流。
- 新服务器任务能力作为并行扩展存在，后续再由客户端页面按需接入。

## 文档索引

- `tools_matrix.md`：预装工具清单、优先级、适合和不适合场景。
- `scenarios.md`：自然语言任务到执行计划和工具调用的映射。
- `api_design.md`：服务器任务 API、状态、SSE、下载和错误格式。
- `docker_runtime.md`：Docker worker、任务目录、资源限制和清理策略。
- `codex_cli_role.md`：Codex CLI 的定位、触发条件、安全边界和降级策略。

## 当前边界

- 本目录只做规划，不创建 Dockerfile、不实现 CLI、不安装依赖。
- 后续代码建议独立放置，不把规划文档和运行时代码混在一起。
- 所有规划默认 `docfusion-cli` 命令前缀为 `docfusion`。
