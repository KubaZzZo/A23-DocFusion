# Codex CLI 角色与接入边界

## 核心定位

Codex CLI 在 DocFusion 服务器版中是**可选的高级任务代理**，不是基础文档处理引擎。

```text
docfusion-cli = 工具层：确定性、快速、可测试、可复用
Codex CLI     = 代理层：规划、判断、组合、处理模糊 L3 任务
```

任何能由 `docfusion-cli` 直接完成的 L1/L2 任务，都不应该交给 Codex CLI。

## 什么时候使用 Codex CLI

只有满足以下条件之一时，才进入 L3 Agent 路径：

| 触发条件 | 示例 |
| --- | --- |
| 用户指令模糊，需要拆解目标 | “帮我把这份材料整理得更正式” |
| 需要多文档融合和内容理解 | “根据这三份材料生成一份项目报告” |
| 需要生成长文档或章节结构 | “写一份可行性研究报告” |
| 需要改写、润色、补全 | “把申报书补完整并改得更正式” |
| 需要根据中间结果决定下一步 | “先看材料内容，再决定怎么分类汇总” |

## 不使用 Codex CLI 的场景

| 场景 | 原因 |
| --- | --- |
| Word 转 PDF | 单条确定性命令即可完成 |
| 修改字体、字号、页边距 | 参数明确，python-docx 更稳定 |
| PDF 合并或拆分 | pypdf/qpdf 更快、更便宜 |
| Excel 转 CSV | pandas 直接完成 |
| OCR 普通图片 | Tesseract 直接完成 |

## 接入架构

```text
后端任务调度器
  -> L1/L2: Docker worker 直接执行 task.json 中的 steps
  -> L3: Docker Codex worker 读取 agent_prompt
        -> Codex CLI 规划
        -> 调用 docfusion-cli
        -> 写入 output/ 和 logs/
```

Codex CLI 必须运行在 Docker 容器中，不直接运行在服务器宿主机。

## 安全边界

Codex CLI 只能访问：

```text
/workspace/input   # 只读
/workspace/work    # 可读写
/workspace/output  # 可读写，最终结果
/workspace/logs    # 可读写，结构化日志
/workspace/task.json
```

明确禁止：

- 访问 `/workspace` 之外的路径。
- 安装新软件或新 Python 包。
- 修改系统配置。
- 访问 Docker socket。
- 访问服务器源码目录。
- 启动后台服务。
- 任意访问外网。
- 把 API Key 写入文件。

L3 容器网络只允许访问 OpenAI API 或用户配置的 LLM API。

## 系统提示模板

Codex CLI 启动时必须注入类似约束：

```markdown
你是 DocFusion 文档处理代理。

规则：
1. 只能在 /workspace 中工作。
2. 输入文件在 /workspace/input，只读。
3. 中间文件写入 /workspace/work。
4. 最终结果必须写入 /workspace/output。
5. 日志写入 /workspace/logs/steps.jsonl。
6. 优先使用 docfusion-cli，不要手写复杂文档处理逻辑。
7. 不要安装新软件或新包。
8. 不要访问 /workspace 之外的路径。
9. 不要修改系统配置。
10. 完成后输出 JSON。

可用命令：
- docfusion convert
- docfusion format-docx
- docfusion fill-template
- docfusion merge
- docfusion split
- docfusion extract
- docfusion ocr
- docfusion generate
- docfusion validate

成功输出：
{"success": true, "files": ["output/..."], "summary": "..."}

失败输出：
{"success": false, "error": "...", "partial_files": ["output/..."], "failed_step": "..."}
```

## 降级策略

Codex CLI 失败时，不自动无限循环重试。

失败处理规则：

1. 保留 `output/` 中已经生成的部分文件。
2. 返回 `partial_files`、`failed_step` 和错误摘要。
3. 标记任务状态为 `failed` 或 `timeout`。
4. 将完整 stdout、stderr、steps.jsonl 保留 72 小时。
5. 如果失败前已完成可用 L1/L2 子任务，前端可以提示用户下载部分结果。

可选的一次性重试只允许在以下情况下发生：

- 网络临时失败。
- LLM API 限流。
- Codex CLI 进程非业务原因退出。

重试次数默认最多 1 次。

## 成本控制

- L1/L2 不走 Agent，节省 API 费用和等待时间。
- L3 默认最多 20 个步骤。
- L3 默认超时 10 分钟，最大 30 分钟。
- Agent prompt 只包含任务目录、可用工具和必要文件摘要，不塞入无关上下文。
- 相同类型任务可复用后端生成的执行计划模板。

## 与 docfusion-cli 的关系

Codex CLI 只能作为 `docfusion-cli` 的上层协调者。

这意味着：

- `docfusion-cli` 必须先完成。
- `docfusion-cli` 命令接口必须稳定。
- Codex CLI 的提示中必须列出 `docfusion` 命令用法。
- 即使没有 Codex CLI，系统仍能处理 L1/L2 任务。

## 后续演进

| 版本 | 目标 |
| --- | --- |
| v1 | 手动触发 Codex CLI 容器，验证 L3 任务可行性 |
| v2 | 后端自动判断是否需要 Agent |
| v3 | Agent 可读取受控数据库或知识库摘要 |
| v4 | 增加结果校验 Agent，但仍受相同容器边界限制 |
