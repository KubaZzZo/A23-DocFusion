# 后端任务 API 设计

## 概述

服务器后端提供 REST API，供本地客户端提交自然语言文档任务、查看状态、监听进度、读取日志和下载结果。第一版复用现有 Bearer Token 认证方式，不改变当前桌面端已有 API。

## 接口列表

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/server-tasks` | 提交任务 |
| `GET` | `/api/server-tasks/{task_id}` | 查询任务状态 |
| `GET` | `/api/server-tasks/{task_id}/events` | SSE 实时进度 |
| `GET` | `/api/server-tasks/{task_id}/logs` | 获取执行日志 |
| `GET` | `/api/server-tasks/{task_id}/download` | 下载结果文件 |
| `DELETE` | `/api/server-tasks/{task_id}` | 取消或删除任务 |
| `GET` | `/api/server-tasks` | 分页列出任务 |

## 提交任务

```http
POST /api/server-tasks
Content-Type: multipart/form-data
Authorization: Bearer {token}
```

### multipart 字段

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `instruction` | string | 是 | 用户自然语言指令 |
| `files[]` | File[] | 是 | 上传文件，第一版限制 1-10 个 |
| `priority` | string | 否 | `normal` 或 `high`，默认 `normal` |
| `timeout` | int | 否 | 任务超时秒数，不得超过该级别最大值 |

### 响应

```json
{
  "task_id": "task_20260522_a1b2c3",
  "status": "queued",
  "level": "L2",
  "created_at": "2026-05-22T12:00:00Z",
  "estimated_duration": 30,
  "position_in_queue": 0
}
```

### 任务状态

| 状态 | 含义 |
| --- | --- |
| `queued` | 已创建，等待执行 |
| `running` | 正在执行 |
| `completed` | 执行成功 |
| `failed` | 工具或 Agent 执行失败 |
| `timeout` | 超过允许时长后被终止 |
| `cancelled` | 用户取消或任务被删除 |

状态流转：

```text
queued -> running -> completed
                  -> failed
                  -> timeout
queued -> cancelled
running -> cancelled
```

## 查询任务状态

```http
GET /api/server-tasks/{task_id}
Authorization: Bearer {token}
```

```json
{
  "task_id": "task_20260522_a1b2c3",
  "status": "running",
  "level": "L2",
  "requires_agent": false,
  "created_at": "2026-05-22T12:00:00Z",
  "started_at": "2026-05-22T12:00:02Z",
  "completed_at": null,
  "progress": {
    "current_step": 2,
    "total_steps": 3,
    "description": "正在转换为 PDF"
  },
  "input_files": ["report.docx"],
  "output_files": [],
  "error": null
}
```

## SSE 实时进度

```http
GET /api/server-tasks/{task_id}/events
Authorization: Bearer {token}
Accept: text/event-stream
```

固定事件类型：

| 事件 | 说明 |
| --- | --- |
| `queued` | 任务进入队列 |
| `step_started` | 某一步开始 |
| `step_completed` | 某一步完成 |
| `progress` | 普通进度消息 |
| `complete` | 任务完成 |
| `error` | 任务失败或超时 |

示例：

```text
event: step_started
data: {"step": 1, "action": "format-docx", "message": "正在修改标题样式"}

event: step_completed
data: {"step": 1, "action": "format-docx", "message": "标题样式修改完成"}

event: complete
data: {"success": true, "files": ["output/report.pdf"], "summary": "已修改标题并转换为 PDF"}
```

## 下载结果

```http
GET /api/server-tasks/{task_id}/download
Authorization: Bearer {token}
```

| 输出数量 | 响应 |
| --- | --- |
| 0 | `404` |
| 1 | 直接返回文件，带 `Content-Disposition: attachment` |
| 多个 | 返回 zip 包 |

可选参数：`?file=output/report.pdf`，用于指定下载单个输出文件。

## 获取日志

```http
GET /api/server-tasks/{task_id}/logs
Authorization: Bearer {token}
```

```json
{
  "task_id": "task_20260522_a1b2c3",
  "logs": [
    {"time": "2026-05-22T12:00:02Z", "level": "info", "message": "任务开始执行"},
    {"time": "2026-05-22T12:00:03Z", "level": "info", "message": "执行 step_1: format-docx"},
    {"time": "2026-05-22T12:00:08Z", "level": "info", "message": "任务完成"}
  ]
}
```

日志来源：

- `logs/steps.jsonl`：结构化步骤日志。
- `logs/stdout.log`：工具标准输出。
- `logs/stderr.log`：工具错误输出。

## 取消或删除任务

```http
DELETE /api/server-tasks/{task_id}
Authorization: Bearer {token}
```

- `queued`：从队列移除并标记 `cancelled`。
- `running`：请求 worker 停止；超时未退出则强制终止容器。
- 已完成任务：删除任务目录或标记待清理，具体实现由保留策略决定。

## 列出任务

```http
GET /api/server-tasks?status=running&limit=20&offset=0
Authorization: Bearer {token}
```

| 参数 | 说明 |
| --- | --- |
| `status` | `queued`、`running`、`completed`、`failed`、`timeout`、`cancelled`、`all` |
| `limit` | 每页数量，默认 20 |
| `offset` | 偏移量 |

## 错误响应

```json
{
  "error": {
    "code": "QUEUE_FULL",
    "message": "任务队列已满，请稍后重试",
    "detail": null
  }
}
```

| 错误码 | 含义 |
| --- | --- |
| `TASK_NOT_FOUND` | 任务不存在 |
| `TASK_EXPIRED` | 任务已过期或被清理 |
| `FILE_TOO_LARGE` | 文件超过大小限制 |
| `UNSUPPORTED_TYPE` | 不支持的文件类型 |
| `QUEUE_FULL` | 队列已满 |
| `EXECUTION_TIMEOUT` | 执行超时 |
| `TOOL_ERROR` | `docfusion-cli` 或预装工具失败 |
| `AGENT_ERROR` | Codex CLI Agent 失败 |

## 上传限制

| 限制项 | 默认值 |
| --- | --- |
| 单文件大小 | 50 MB |
| 总上传大小 | 200 MB |
| 文件数量 | 10 |
| 允许类型 | docx、xlsx、pptx、pdf、txt、md、html、csv、jpg、png、tiff |

上传后先执行大小检查、magic bytes 类型验证和可选 Office 宏检查。

## 认证

第一版复用现有 Bearer Token。服务器部署时再增加以下能力：

- 客户端 API Key 或 JWT。
- 可配置 IP 白名单。
- HTTPS 反向代理。
- 任务级审计日志。
